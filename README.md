# AutoUpdate-GitHubIPAllowList-Fabric

## About
This sample program aim to update GitHub Enterprise Cloud - IP Allow list configuration with the current Fabric outbound IPs for specific region to allow Fabric Git Integration to work with this enterpeise instance.

## Diagram
![alt text](img/fabric-ip-allow-list.png)

## How the solution works
Based on scheduled interval the program will start:
1. Get the updated list of Fabric outbound IP for the request region (tag name: PowerBI.X) 
1. Connect to GitHub Enterprise Cloud instance and find which IPs need to be added / deleted / unchanged using GraphQL Github API
1. Add / Delete the IPs

### Prerequisites

- Azure subscription with Microsoft.Network register
```
az provider register --namespace Microsoft.Network
```
- Assign 'reader' permission to Azure subscription to either: 
```
Newly created service principal in same Azure subscription (grab the tenat id, client id, client secret) 
OR
Use of Azure Managed Identity - for this you will need to run the container on Azure service with identity assigned

```
- GitHub PAT which has the following scope for your GitHub Enterprise Cloud: admin:enterprise, read:org


## How to build the container and execute
- Build the docker image
```
while in the root folder execute:
docker build -t allowlistupdater .
```
- Run the following docker command
```
docker run -d -e AZURE_SUBSCRIPTION_ID=<ID> -e GITHUB_TOKEN=<TOKEN>  -e GITHUB_ENTERPRISE=<NAME> -e FABRIC_REGION=<azure region> -e IP_ALLOW_LIST_MODE=<execution for actual run> -e RUN_INTERVAL_MINUTES=<INTERVAL in MIN> -e AZURE_CLIENT_ID=<S{N Client ID}> -e AZURE_TENANT_ID=<TENANT ID> -e AZURE_CLIENT_SECRET=<SPN secret> allowlistupdater
```

