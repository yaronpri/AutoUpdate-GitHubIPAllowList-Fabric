from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
import requests
import os
import json


def get_github_headers():
    """Get headers for GitHub GraphQL API"""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable is required")
    
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def get_enterprise_info(enterprise_slug):
    """Get GitHub Enterprise basic info"""
    query = """
    query($slug: String!) {
      enterprise(slug: $slug) {
        id
        slug
        name
        databaseId
        url
      }
    }
    """
    
    variables = {"slug": enterprise_slug}
    
    response = requests.post(
        "https://api.github.com/graphql",
        headers=get_github_headers(),
        json={"query": query, "variables": variables}
    )
    
    if response.status_code != 200:
        raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
    
    data = response.json()
    
    # Check for errors in the response
    if "errors" in data:
        raise Exception(f"GraphQL errors: {data['errors']}")
    
    if not data.get("data", {}).get("enterprise"):
        raise Exception(f"Enterprise '{enterprise_slug}' not found or you don't have access to it")
    
    return data["data"]["enterprise"]


def get_current_ip_allow_list_enterprise(enterprise_slug, cursor=None):
    """Get current IP allow list from GitHub Enterprise using the correct query"""
    query = """
    query getEnterprise($enterpriseName: String!, $cursor: String) {
        enterprise(slug: $enterpriseName) {
            databaseId
            name
            slug
            url,
            id,
            ownerInfo {
                ipAllowListEntries(first: 100, after: $cursor) {
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                    totalCount
                    nodes {
                        id
                        name
                        createdAt
                        updatedAt
                        isActive
                        allowListValue
                    }
                }
            }
        }
    }
    """
    
    variables = {
        "enterpriseName": enterprise_slug,
        "cursor": cursor
    }
    
    response = requests.post(
        "https://api.github.com/graphql",
        headers=get_github_headers(),
        json={"query": query, "variables": variables}
    )
    
    if response.status_code != 200:
        raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
    
    data = response.json()
    
    # Check for errors in the response
    if "errors" in data:
        raise Exception(f"GraphQL errors: {data['errors']}")
    
    return data


def get_all_ip_allow_list_entries(enterprise_slug):
    """Get all IP allow list entries, handling pagination"""
    all_entries = []
    cursor = None
    has_next_page = True
    
    while has_next_page:
        result = get_current_ip_allow_list_enterprise(enterprise_slug, cursor)
        
        if not result.get("data", {}).get("enterprise", {}).get("ownerInfo"):
            print("No ownerInfo found - this might mean IP allow list is not enabled or you don't have permissions")
            break
            
        ip_entries = result["data"]["enterprise"]["ownerInfo"]["ipAllowListEntries"]
        all_entries.extend(ip_entries["nodes"])
        
        page_info = ip_entries["pageInfo"]
        has_next_page = page_info["hasNextPage"]
        cursor = page_info["endCursor"] if has_next_page else None
        
        print(f"Fetched {len(ip_entries['nodes'])} entries, total so far: {len(all_entries)}")
    
    return all_entries


def add_ip_to_allow_list(owner_id, ip_range, name, is_active=True):
    """Add an IP range to GitHub's IP allow list"""
    mutation = """
    mutation($input: CreateIpAllowListEntryInput!) {
      createIpAllowListEntry(input: $input) {
        ipAllowListEntry {
          id
          allowListValue
          name
          isActive
        }
        clientMutationId
      }
    }
    """
    
    variables = {
        "input": {
            "ownerId": owner_id,
            "allowListValue": ip_range,
            "name": name,
            "isActive": is_active
        }
    }
    
    response = requests.post(
        "https://api.github.com/graphql",
        headers=get_github_headers(),
        json={"query": mutation, "variables": variables}
    )
    
    if response.status_code != 200:
        raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
    
    return response.json()


def delete_ip_from_allow_list(entry_id):
    """Delete an IP range from GitHub's IP allow list"""
    mutation = """
    mutation($input: DeleteIpAllowListEntryInput!) {
      deleteIpAllowListEntry(input: $input) {
        ipAllowListEntry {
          id
        }
        clientMutationId
      }
    }
    """
    
    variables = {
        "input": {
            "ipAllowListEntryId": entry_id
        }
    }
    
    response = requests.post(
        "https://api.github.com/graphql",
        headers=get_github_headers(),
        json={"query": mutation, "variables": variables}
    )
    
    if response.status_code != 200:
        raise Exception(f"GitHub API error: {response.status_code} - {response.text}")
    
    return response.json()


def update_github_ip_allowlist(filtered_ips, enterprise_slug, tag_prefix="PowerBI-IsraelCentral"):
    """Update GitHub Enterprise IP allow list with new IP ranges"""
    try:
        # Get enterprise info
        enterprise_info = get_enterprise_info(enterprise_slug)
        print(f"Enterprise: {enterprise_info['name']} ({enterprise_info['slug']})")
        print(f"Enterprise ID: {enterprise_info['id']}")
        
        # Get all current IP allow list entries
        print("Fetching current IP allow list entries...")
        current_entries = get_all_ip_allow_list_entries(enterprise_slug)
        
        print(f"Current IP allow list entries: {len(current_entries)}")
        
        # Find entries that match our tag prefix (PowerBI entries we manage)
        our_entries = [entry for entry in current_entries if entry["name"] and entry["name"].startswith(tag_prefix)]
        
        print(f"Found {len(our_entries)} existing {tag_prefix} entries")
        
        # Show current entries for reference
        if our_entries:
            print("Existing PowerBI entries:")
            for entry in our_entries:
                print(f"  - {entry['name']}: {entry['allowListValue']} (Active: {entry['isActive']})")
        
        # Delete existing PowerBI entries
        for entry in our_entries:
            print(f"Deleting existing entry: {entry['name']} - {entry['allowListValue']}")
            delete_result = delete_ip_from_allow_list(entry["id"])
            if "errors" in delete_result:
                print(f"Error deleting entry: {delete_result['errors']}")
            else:
                print(f"Successfully deleted: {entry['allowListValue']}")
        
        # Add new IP ranges
        success_count = 0
        for i, ip_range in enumerate(filtered_ips):
            entry_name = f"{tag_prefix}-{i+1:03d}"  # Zero-pad for better sorting
            print(f"Adding IP range: {entry_name} - {ip_range}")
            
            add_result = add_ip_to_allow_list(enterprise_info["id"], ip_range, entry_name)
            
            if "errors" in add_result:
                print(f"Error adding IP range {ip_range}: {add_result['errors']}")
            else:
                print(f"Successfully added: {ip_range}")
                success_count += 1
        
        print(f"\n✅ GitHub Enterprise IP allow list updated!")
        print(f"   Added: {success_count}/{len(filtered_ips)} PowerBI IP ranges")
        print(f"   Removed: {len(our_entries)} old PowerBI entries")
        
    except Exception as e:
        print(f"❌ Error updating GitHub Enterprise IP allow list: {e}")


def main():
    # Azure Service Tags
    print("Fetching PowerBI Israel Central IP ranges from Azure Service Tags...")
    client = NetworkManagementClient(
        credential=DefaultAzureCredential(),
        subscription_id="88c3aa4a-3792-4816-8eda-300a20feb190",
    )

    response = client.service_tags.list(
        location="israelcentral",
    )
    
    filtered_ips = []
    for tag in response.values:
        if tag.id == "PowerBI.IsraelCentral":
            for ip in tag.properties.address_prefixes:
                filtered_ips.append(ip)
    
    print(f"Found {len(filtered_ips)} PowerBI Israel Central IP ranges:")
    for i, ip in enumerate(filtered_ips[:5]):  # Show first 5
        print(f"  - {ip}")
    if len(filtered_ips) > 5:
        print(f"  ... and {len(filtered_ips) - 5} more")
    
    # GitHub Enterprise configuration
    github_enterprise = os.getenv("GITHUB_ENTERPRISE", "")
    
    if not github_enterprise:
        print("\nPlease set GITHUB_ENTERPRISE environment variable with your GitHub Enterprise slug")
        print("Example: export GITHUB_ENTERPRISE='my-company'")
        return
    
    # Update GitHub Enterprise IP allow list
    print(f"\nUpdating GitHub Enterprise IP allow list for: {github_enterprise}")
    update_github_ip_allowlist(filtered_ips, github_enterprise)


if __name__ == "__main__":
    main()