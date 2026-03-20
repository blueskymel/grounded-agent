// ============================================================
// GroundedAgent — API Management module
// Scope: resource group
// SKU: Consumption (serverless, per-call billing, no monthly base)
// Creates: APIM instance, API definition, rate-limit + CORS policy,
//          subscription-key protected product, backend pointing at ACA.
// ============================================================

@description('Azure region for the APIM instance.')
param location string = resourceGroup().location

@description('Publisher email address (required by APIM).')
param publisherEmail string

@description('Publisher organisation display name.')
param publisherName string = 'GroundedAgent'

@description('FQDN of the backend API target, without scheme (for example Container App or Function App hostname).')
param backendFqdn string

// ------ Naming ---------------------------------------------------------------
var suffix   = take(uniqueString(resourceGroup().id), 8)
var apimName = 'apim-grounded-${suffix}'

// ------ APIM service ---------------------------------------------------------
resource apim 'Microsoft.ApiManagement/service@2022-08-01' = {
  name: apimName
  location: location
  sku: {
    name: 'Consumption'
    capacity: 0  // Consumption tier always uses capacity 0
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
  }
}

// ------ Backend --------------------------------------------------------------
resource backend 'Microsoft.ApiManagement/service/backends@2022-08-01' = {
  parent: apim
  name: 'grounded-agent-backend'
  properties: {
    url: 'https://${backendFqdn}'
    protocol: 'http'
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}

// ------ Product (subscription-key gating) ------------------------------------
resource product 'Microsoft.ApiManagement/service/products@2022-08-01' = {
  parent: apim
  name: 'grounded-agent'
  properties: {
    displayName: 'GroundedAgent API'
    description: 'Grounded RAG copilot for IT Ops and Retail enterprise workflows.'
    subscriptionRequired: true
    approvalRequired: false
    state: 'published'
  }
}

// ------ API ------------------------------------------------------------------
resource api 'Microsoft.ApiManagement/service/apis@2022-08-01' = {
  parent: apim
  name: 'grounded-agent-api'
  properties: {
    displayName: 'GroundedAgent API'
    description: 'Grounded RAG copilot API. Subscription key required via Ocp-Apim-Subscription-Key header.'
    subscriptionRequired: true
    path: ''
    protocols: ['https']
    serviceUrl: 'https://${backendFqdn}'
    subscriptionKeyParameterNames: {
      header: 'Ocp-Apim-Subscription-Key'
      query: 'subscription-key'
    }
  }
}

// ------ API-level policy: rate limit + CORS ----------------------------------
resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2022-08-01' = {
  parent: api
  name: 'policy'
  properties: {
    format: 'xml'
    value: '''<policies>
  <inbound>
    <base />
    <rate-limit calls="60" renewal-period="60" />
    <cors allow-credentials="false">
      <allowed-origins>
        <origin>*</origin>
      </allowed-origins>
      <allowed-methods>
        <method>GET</method>
        <method>POST</method>
        <method>OPTIONS</method>
      </allowed-methods>
      <allowed-headers>
        <header>*</header>
      </allowed-headers>
    </cors>
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
  </outbound>
  <on-error>
    <base />
  </on-error>
</policies>'''
  }
}

// ------ Link API to product --------------------------------------------------
resource productApi 'Microsoft.ApiManagement/service/products/apis@2022-08-01' = {
  parent: product
  name: api.name
}

// ------ Operations -----------------------------------------------------------
resource opHealth 'Microsoft.ApiManagement/service/apis/operations@2022-08-01' = {
  parent: api
  name: 'health-check'
  properties: {
    displayName: 'Health Check'
    method: 'GET'
    urlTemplate: '/health'
    description: 'Returns API health status and retrieval backend mode.'
    responses: [{ statusCode: 200, description: 'Healthy' }]
  }
}

resource opKbStats 'Microsoft.ApiManagement/service/apis/operations@2022-08-01' = {
  parent: api
  name: 'kb-stats'
  properties: {
    displayName: 'Knowledge Base Stats'
    method: 'GET'
    urlTemplate: '/kb/stats'
    description: 'Returns document counts and retrieval backend metadata.'
    responses: [{ statusCode: 200, description: 'KB statistics' }]
  }
}

resource opChat 'Microsoft.ApiManagement/service/apis/operations@2022-08-01' = {
  parent: api
  name: 'chat'
  properties: {
    displayName: 'Chat'
    method: 'POST'
    urlTemplate: '/chat'
    description: 'Submit a question and receive a grounded answer with citations.'
    request: {
      description: 'ChatRequest body'
      representations: [{ contentType: 'application/json' }]
    }
    responses: [{ statusCode: 200, description: 'Grounded answer with citations' }]
  }
}

resource opChatStream 'Microsoft.ApiManagement/service/apis/operations@2022-08-01' = {
  parent: api
  name: 'chat-stream'
  properties: {
    displayName: 'Chat (Streaming)'
    method: 'POST'
    urlTemplate: '/chat/stream'
    description: 'Server-sent event stream of grounded answer chunks.'
    request: {
      representations: [{ contentType: 'application/json' }]
    }
    responses: [{ statusCode: 200, description: 'SSE stream' }]
  }
}

// ------ Outputs --------------------------------------------------------------
output apimGatewayUrl string = apim.properties.gatewayUrl
output apimName        string = apim.name
