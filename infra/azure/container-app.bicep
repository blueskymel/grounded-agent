// ============================================================
// GroundedAgent — Azure Container Apps module
// Scope: resource group
// Creates: Log Analytics, ACR, Container Apps Environment, Container App
// ACR pulls use a user-assigned managed identity (no admin credentials).
// ============================================================

@description('Azure region for all resources.')
param location string = resourceGroup().location

@description('Short environment tag used in naming (e.g. dev, prod).')
param environmentName string

@description('Container image reference, e.g. myregistry.azurecr.io/api:latest.')
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

@description('Set to true to provision Key Vault and configure the app to resolve secrets using managed identity.')
param deployKeyVault bool = false

@description('Secret name for Azure OpenAI API key in Key Vault.')
param azureOpenAiApiKeySecretName string = 'azure-openai-api-key'

@description('Secret name for Azure AI Search API key in Key Vault.')
param azureSearchApiKeySecretName string = 'azure-search-api-key'

@description('Secret name for Application Insights connection string in Key Vault.')
param appInsightsConnectionStringSecretName string = 'applicationinsights-connection-string'

// ------ Naming ---------------------------------------------------------------
var suffix           = take(uniqueString(resourceGroup().id), 8)
var logAnalyticsName = 'law-grounded-${suffix}'
var containerEnvName = 'cae-grounded-${environmentName}'
var registryName     = 'acrgrounded${suffix}'
var keyVaultName     = 'kvgrounded${suffix}'
var identityName     = 'id-grounded-${suffix}'
var containerAppName = 'ca-grounded-agent'

// ------ Log Analytics Workspace ----------------------------------------------
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ------ Azure Container Registry ---------------------------------------------
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false // managed identity used for pulls
  }
}

// ------ User-Assigned Managed Identity (for ACR pulls) ----------------------
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

// AcrPull built-in role ID
var acrPullRoleId = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, acrPullRoleId)
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      acrPullRoleId
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = if (deployKeyVault) {
  name: keyVaultName
  location: location
  properties: {
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enabledForDeployment: false
    enabledForTemplateDeployment: false
    enabledForDiskEncryption: false
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
    sku: {
      family: 'A'
      name: 'standard'
    }
  }
}

resource keyVaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (deployKeyVault) {
  name: guid(keyVault.id, identity.id, keyVaultSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      keyVaultSecretsUserRoleId
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// ------ Container Apps Environment -------------------------------------------
resource containerEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ------ Container App --------------------------------------------------------
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    managedEnvironmentId: containerEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'OPTIONS']
          allowedHeaders: ['*']
        }
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: identity.id
        }
      ]
      secrets: deployKeyVault
        ? []
        : [
            { name: 'openai-api-key', value: azureOpenAiApiKey }
            { name: 'search-api-key', value: azureSearchApiKey }
            { name: 'appinsights-cs', value: appInsightsConnectionString }
          ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: concat(
            [
              { name: 'APP_ENV',                            value: 'production' }
              { name: 'RETRIEVAL_BACKEND',                  value: 'azure_search' }
              { name: 'AZURE_OPENAI_ENDPOINT',              value: azureOpenAiEndpoint }
              { name: 'AZURE_OPENAI_API_VERSION',           value: '2024-10-21' }
              { name: 'AZURE_OPENAI_CHAT_DEPLOYMENT',       value: azureOpenAiChatDeployment }
              { name: 'AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT', value: azureOpenAiEmbeddingsDeployment }
              { name: 'AZURE_SEARCH_ENDPOINT',              value: azureSearchEndpoint }
              { name: 'AZURE_SEARCH_INDEX_NAME',            value: azureSearchIndexName }
            ],
            deployKeyVault
              ? [
                  { name: 'KEY_VAULT_URL',                                             value: any(keyVault).properties.vaultUri }
                  { name: 'MANAGED_IDENTITY_CLIENT_ID',                                value: identity.properties.clientId }
                  { name: 'KEYVAULT_AZURE_OPENAI_API_KEY_SECRET_NAME',                 value: azureOpenAiApiKeySecretName }
                  { name: 'KEYVAULT_AZURE_SEARCH_API_KEY_SECRET_NAME',                 value: azureSearchApiKeySecretName }
                  { name: 'KEYVAULT_APPLICATIONINSIGHTS_CONNECTION_STRING_SECRET_NAME', value: appInsightsConnectionStringSecretName }
                ]
              : [
                  { name: 'AZURE_OPENAI_API_KEY',                  secretRef: 'openai-api-key' }
                  { name: 'AZURE_SEARCH_API_KEY',                  secretRef: 'search-api-key' }
                  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-cs' }
                ]
          )
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: { concurrentRequests: '20' }
            }
          }
        ]
      }
    }
  }
  dependsOn: deployKeyVault ? [acrPull, keyVaultSecretsUser] : [acrPull]
}

// ------ Outputs --------------------------------------------------------------
output registryLoginServer string = registry.properties.loginServer
output registryName        string = registry.name
output containerAppFqdn    string = containerApp.properties.configuration.ingress.fqdn
output containerAppName    string = containerApp.name
output identityClientId    string = identity.properties.clientId
output keyVaultName        string = deployKeyVault ? keyVault.name : ''
output keyVaultUrl         string = deployKeyVault ? any(keyVault).properties.vaultUri : ''
