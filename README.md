# AutoUpdate-GitHubIPAllowList-Fabric

## About
This sample program aim to update GitHub Enterprise Cloud - IP Allow list configuration with the current Fabric outbound IPs for specific region to allow Fabric Git Integration to work with this enterpeise instance.

## Diagram
![alt text](img/fabric-ip-allow-list.png)

## How the solution works
Based on scheduled interval the docker container will perform:
1. Get the updated list of Fabric outbound IP for the request region (tag name: PowerBI.X) 
1. Connect to GitHub Enterprise Cloud instance and find which IPs need to be added / deleted / unchanged using GraphQL Github API
1. Add / Delete the IPs

### Prerequisites

- Azure subscription with Microsoft.Network register
```
az provider register --namespace Microsoft.Network
```
- Create service principal in same Azure subscription (grab the tenant id, client id, client secret) and assign 'reader' permission to Azure subscription
- GitHub PAT which has the following scope for your GitHub Enterprise Cloud: ```admin:enterprise, read:org```
- IMPROTANT: The IP where you host the docker container need to be allowed in IP allow list of your GitHub Enterprise Cloud instance

## How to execute the docker image
- Downdload the docker image
```
docker pull ghcr.io/yaronpri/fabric-ipallowlist-updater:latest
```
- Run the following docker command
```
docker run -d -e AZURE_SUBSCRIPTION_ID=<ID> -e GITHUB_TOKEN=<TOKEN>  -e GITHUB_ENTERPRISE=<NAME> -e FABRIC_REGION=<azure region> -e IP_ALLOW_LIST_MODE=<execution for actual run> -e RUN_INTERVAL_MINUTES=<INTERVAL in MIN> -e AZURE_CLIENT_ID=<S{N Client ID}> -e AZURE_TENANT_ID=<TENANT ID> -e AZURE_CLIENT_SECRET=<SPN secret> ghcr.io/yaronpri/fabric-ipallowlist-updater:latest
```

- You can host this solution on Azure services like: Azure app container , Azure container instance or even Azure VM, make sure you know the outbound ip that the Azure service will use, as its need to be configure as part of the IP allow list

