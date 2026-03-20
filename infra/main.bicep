// ============================================================
// GroundedAgent — azd entry point
// Scope: subscription  (azd deploys at subscription scope)
// Creates a resource group then calls the container-app module.
// ============================================================
targetScope = 'subscription'

@minLength(1)
@maxLength(64)
@description('Name of the environment (drives resource names and tags).')
param environmentName string

@minLength(1)
@description('Primary Azure region for all resources.')
param location string

@description('Container image to deploy. azd sets this after build+push.')
param containerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Azure OpenAI endpoint URL.')
param azureOpenAiEndpoint string = ''

@secure()
@description('Azure OpenAI API key.')
param azureOpenAiApiKey string = ''

@description('Azure OpenAI chat completion deployment name.')
param azureOpenAiChatDeployment string = 'gpt-4o'

@description('Azure OpenAI embeddings deployment name.')
param azureOpenAiEmbeddingsDeployment string = 'text-embedding-3-small'

@description('Azure AI Search endpoint URL.')
param azureSearchEndpoint string = ''

@secure()
@description('Azure AI Search API key.')
param azureSearchApiKey string = ''

@description('Azure AI Search index name.')
param azureSearchIndexName string = 'groundedagent-chunks'

@secure()
@description('Application Insights connection string (optional).')
param appInsightsConnectionString string = ''

@description('Set to true to provision API Management (Consumption) in front of the Container App.')
param deployApim bool = false

@description('Publisher email required by APIM. Used only when deployApim is true.')
param publisherEmail string = 'admin@example.com'

@description('Publisher organisation name for APIM.')
param publisherName string = 'GroundedAgent'

var tags = {
  'azd-env-name': environmentName
  project: 'grounded-agent'
}

// ------ Resource Group -------------------------------------------------------
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-grounded-agent-${environmentName}'
  location: location
  tags: tags
}

// ------ App Module -----------------------------------------------------------
module app './azure/container-app.bicep' = {
  name: 'grounded-agent-app'
  scope: rg
  params: {
    location: location
    environmentName: environmentName
    containerImage: containerImage
    azureOpenAiEndpoint: azureOpenAiEndpoint
    azureOpenAiApiKey: azureOpenAiApiKey
    azureOpenAiChatDeployment: azureOpenAiChatDeployment
    azureOpenAiEmbeddingsDeployment: azureOpenAiEmbeddingsDeployment
    azureSearchEndpoint: azureSearchEndpoint
    azureSearchApiKey: azureSearchApiKey
    azureSearchIndexName: azureSearchIndexName
    appInsightsConnectionString: appInsightsConnectionString
  }
}

// ------ APIM Module (optional) ----------------------------------------------
module apimModule './azure/apim.bicep' = if (deployApim) {
  name: 'grounded-agent-apim'
  scope: rg
  params: {
    location: location
    publisherEmail: publisherEmail
    publisherName: publisherName
    containerAppFqdn: app.outputs.containerAppFqdn
  }
}

// ------ Outputs (azd reads these to wire up the service) --------------------
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = app.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME     string = app.outputs.registryName
output SERVICE_API_URI                   string = deployApim ? apimModule.outputs.apimGatewayUrl : 'https://${app.outputs.containerAppFqdn}'
output SERVICE_API_CONTAINER_APP_NAME    string = app.outputs.containerAppName
output APIM_GATEWAY_URL                  string = deployApim ? apimModule.outputs.apimGatewayUrl : ''
output RESOURCE_GROUP_NAME               string = rg.name
