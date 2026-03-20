// ============================================================
// GroundedAgent — Azure Functions module
// Scope: resource group
// Creates: Storage, Consumption plan, Function App (Python), App Insights
// ============================================================

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Short environment tag used in naming (e.g. dev, prod).')
param environmentName string

@description('Azure OpenAI endpoint URL.')
param azureOpenAiEndpoint string = ''

@secure()
@description('Azure OpenAI API key.')
param azureOpenAiApiKey string = ''

@description('Azure OpenAI chat completion deployment name.')
param azureOpenAiChatDeployment string = 'gpt-4o'

@description('Azure OpenAI embeddings deployment name.')
param azureOpenAiEmbeddingsDeployment string = 'text-embedding-3-small'

@description('Azure AI Search service endpoint URL.')
param azureSearchEndpoint string = ''

@secure()
@description('Azure AI Search admin or query API key.')
param azureSearchApiKey string = ''

@description('Azure AI Search index name.')
param azureSearchIndexName string = 'groundedagent-chunks'

@secure()
@description('Application Insights connection string (optional telemetry export).')
param appInsightsConnectionString string = ''

var suffix = take(uniqueString(resourceGroup().id), 8)
var storageName = 'stgrounded${suffix}'
var planName = 'asp-grounded-${suffix}'
var functionAppName = 'func-grounded-${environmentName}-${suffix}'
var appInsightsName = 'appi-grounded-${suffix}'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    IngestionMode: 'ApplicationInsights'
  }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  kind: 'functionapp'
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      ftpsState: 'Disabled'
      alwaysOn: false
      appSettings: [
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
        {
          name: 'APP_ENV'
          value: 'production'
        }
        {
          name: 'RETRIEVAL_BACKEND'
          value: 'azure_search'
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: azureOpenAiEndpoint
        }
        {
          name: 'AZURE_OPENAI_API_KEY'
          value: azureOpenAiApiKey
        }
        {
          name: 'AZURE_OPENAI_API_VERSION'
          value: '2024-10-21'
        }
        {
          name: 'AZURE_OPENAI_CHAT_DEPLOYMENT'
          value: azureOpenAiChatDeployment
        }
        {
          name: 'AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT'
          value: azureOpenAiEmbeddingsDeployment
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: azureSearchEndpoint
        }
        {
          name: 'AZURE_SEARCH_API_KEY'
          value: azureSearchApiKey
        }
        {
          name: 'AZURE_SEARCH_INDEX_NAME'
          value: azureSearchIndexName
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: empty(appInsightsConnectionString) ? appInsights.properties.ConnectionString : appInsightsConnectionString
        }
      ]
    }
  }
}

output functionAppName string = functionApp.name
output functionAppHostname string = functionApp.properties.defaultHostName