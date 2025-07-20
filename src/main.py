import sys, requests, os, json, logging
from asyncio.log import logger
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler(sys.stdout))

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
        logger.info("No ownerInfo found - this might mean IP allow list is not enabled or you don't have permissions")
        break
          
      ip_entries = result["data"]["enterprise"]["ownerInfo"]["ipAllowListEntries"]
      all_entries.extend(ip_entries["nodes"])
      
      page_info = ip_entries["pageInfo"]
      has_next_page = page_info["hasNextPage"]
      cursor = page_info["endCursor"] if has_next_page else None
      
      logger.info(f"Fetched {len(ip_entries['nodes'])} entries, total so far: {len(all_entries)}")
    
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


def update_github_ip_allowlist(filtered_ips, enterprise_slug, tag_prefix, executation_mode):
  """Update GitHub Enterprise IP allow list with new IP ranges"""
  try:
    # Get enterprise info
    enterprise_info = get_enterprise_info(enterprise_slug)

    # Get all current IP allow list entries
    logger.info(f"Fetching current IP allow list entries for Enterprise: {enterprise_info['name']} ({enterprise_info['slug']}) Enterprise ID: {enterprise_info['id']}")
    current_entries = get_all_ip_allow_list_entries(enterprise_slug)
    
    logger.info(f"Current count of IP allow list entries configure: {len(current_entries)}")
    
    our_entries = []
    for entry in current_entries:
      if (entry["name"] and entry["name"].startswith(tag_prefix)):
        entry["allowListValue"] = entry["allowListValue"].strip()
        our_entries.append(entry)

    logger.info(f"Current count of Fabric IP allow list entries configure: {len(our_entries)}")

    todelete_entries = []
    exist_count = 0
    for entry in our_entries:
      found = False
      for obj in filtered_ips:
        if obj['ip'] == entry["allowListValue"]:
          obj['state'] = 1
          logger.info(f"IP {obj['ip']} already exists in allow list as {entry['allowListValue']}")
          found = True
          exist_count += 1
          break
      if not found:
        todelete_entries.append(entry)  
    
    logger.info(f"Unchanged {exist_count} Fabric IP allow list entries")
    logger.info(f"Need to add: {len(filtered_ips) - exist_count} Fabric IP allow list entries")
    logger.info(f"Need to delete: {len(todelete_entries)} Fabric IP allow list entries")

    if executation_mode:
      # Delete existing Fabric entries
      for entry in todelete_entries:
        logger.info(f"Deleting existing entry: {entry['name']} - {entry['allowListValue']}")
        delete_result = delete_ip_from_allow_list(entry["id"])
        if "errors" in delete_result:
          logger.info(f"Error deleting entry: {delete_result['errors']}")
        else:
          logger.info(f"Successfully deleted: {entry['allowListValue']}")
      
      # Add new IP ranges
      success_count = 0
      error_count = 0
      for i, ip_range in enumerate(filtered_ips):
        entry_name = f"{tag_prefix}-{i+1:03d}"  # Zero-pad for better sorting
        logger.info(f"Adding IP range: {entry_name} - {ip_range}")
        
        if (ip_range['state'] == 0):
          add_result = add_ip_to_allow_list(enterprise_info["id"], ip_range['ip'], entry_name)            
          if "errors" in add_result:
            logger.error(f"Error adding IP range {ip_range}: {add_result['errors']}")
          else:
            logger.info(f"Successfully added: {ip_range}")
            success_count += 1
      
      logger.info(f"GitHub Enterprise IP allow list updated!")
      logger.info(f"   Added: {success_count} Failed: {error_count} Fabric IP ranges")
      logger.info(f"   Removed: {len(todelete_entries)} old Fabric IP entries")
      logger.info(f"   Not changed: {exist_count} Fabric IP entries")
    
  except Exception as e:
    logger.info(f"Error updating GitHub Enterprise IP allow list: {e}")


def main():

  logger.info(f"Start Allow List update process at {datetime.now()}")

  azure_sub_id = os.getenv("AZURE_SUBSCRIPTION_ID", "")
  github_enterprise = os.getenv("GITHUB_ENTERPRISE", "")
  region = os.getenv("FABRIC_REGION", "")
  github_token = os.getenv("GITHUB_TOKEN", "")
  executation_mode = os.getenv("IP_ALLOW_LIST_MODE", "whatif").lower() == "execution"
  
  if not azure_sub_id:
    logger.error("AZURE_SUBSCRIPTION_ID environment variable is required.")
    return
  if not region:
    logger.error("FABRIC_REGION environment variable is required - your fabric home tenant region.")
    return
  if not github_enterprise:
    logger.info("\nPlease set GITHUB_ENTERPRISE environment variable with your GitHub Enterprise slug")
    logger.info("Example: export GITHUB_ENTERPRISE='my-company'")
    return
  if not github_token:
    logger.error("GITHUB_TOKEN environment variable is required. PAT scope require:admin:enterprise, read:org ")
    return

  if not executation_mode:
    logger.info(f"Execution mode is: {executation_mode} - to run actual operation set env variable IP_ALLOW_LIST_MODE to execution")
  else:
    logger.info("** NOTICE: REAL MODE EXECUTION **")

  # Azure Service Tags
  logger.info(f"Fetching Fabric {region} IP ranges from Azure Service Tags...")
  client = NetworkManagementClient(
      credential=DefaultAzureCredential(),
      subscription_id=azure_sub_id,
  )

  response = client.service_tags.list(
      location=region,
  )  
  powerbi_tag_prefix = f"PowerBI.{region}".lower()

  filtered_ips = []
  for tag in response.values:
      # Check if the tag ID matches PowerBI for the specified region
      if tag.id.lower() == powerbi_tag_prefix:
          for ip in tag.properties.address_prefixes:
              filtered_ips.append({'ip':ip, 'state':0})
  
  logger.info(f"Found {len(filtered_ips)} Fabric {region} IP ranges:")
  for i, ip in enumerate(filtered_ips):  
      logger.info(f"  - {ip}")

  
  # Update GitHub Enterprise IP allow list
  logger.info(f"\nUpdating GitHub Enterprise IP allow list for: {github_enterprise}")
  fabric_tag_prefix = f"Fabric.{region}".lower()
  update_github_ip_allowlist(filtered_ips, github_enterprise, fabric_tag_prefix, executation_mode)

  logger.info(f"End Allow List update process at {datetime.now()}")
if __name__ == "__main__":
  main()