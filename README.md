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
- Azure Identity 
```
Create service principal in same subscription (grab the tenat id, client id, client secret) 
OR
use of Azure Managed Identity - for this you will beed to run this program on Azure with identity assigned to the hosted service
```
- GitHub PAT which has the following scope for your GitHub Enterprise Cloud: admin:enterprise, read:org


## How to execute the program
- Set following environment variable
```
GITHUB_ENTERPRISE = <GITHUB ENTERPRISE NAME>
GITHUB_TOKEN = <PAT TOKEN>
FABRIC_REGION = <YOUR FABRIC HOME TENANT REGION>
AZURE_SUBSCRIPTION_ID=<AZURE SUBSCRIPTION ID>
IP_ALLOW_LIST_MODE = <DEFAULT is to run in dryrun, to actual perform the update operation set this value to execution>

```