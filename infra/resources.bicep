param environmentName string
param location string
param tags object
param modelName string
param modelVersion string
param modelCapacity int
param enableStorage bool = false

var token = toLower(uniqueString(subscription().id, resourceGroup().id, environmentName))
var prefix = take(replace(toLower(environmentName), '-', ''), 12)
var aiSubdomain = '${prefix}-ai-${token}'

var storageEnv = enableStorage
  ? [
      { name: 'AZURE_STORAGE_ACCOUNT_URL', value: storage.?properties.primaryEndpoints.blob ?? '' }
      { name: 'AZURE_STORAGE_CONTAINER', value: 'bukti' }
    ]
  : []

var roles = {
  acrPull: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
  openAiUser: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
  mapsDataReader: '423170ca-a8f6-4b0f-8487-9e4eb8f49bfa'
  blobContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-id-${token}'
  location: location
  tags: tags
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${prefix}-log-${token}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: {
      dailyQuotaGb: json('0.1')
    }
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${prefix}-appi-${token}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: '${prefix}acr${token}'
  location: location
  tags: tags
  sku: { name: 'Basic' }
  properties: {
    adminUserEnabled: false
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = if (enableStorage) {
  name: '${take(prefix, 8)}st${take(token, 10)}'
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowSharedKeyAccess: false
    allowBlobPublicAccess: false
    publicNetworkAccess: 'Enabled'
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
    }
  }

  resource blob 'blobServices@2023-05-01' = {
    name: 'default'
    properties: {
      isVersioningEnabled: true
    }

    resource container 'containers@2023-05-01' = {
      name: 'bukti'
    }
  }
}

resource ai 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: '${prefix}-ai-${token}'
  location: location
  tags: tags
  kind: 'AIServices'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: aiSubdomain
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource model 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: ai
  name: modelName
  sku: {
    name: 'GlobalStandard'
    capacity: modelCapacity
  }
  properties: {
    model: union(
      { format: 'OpenAI', name: modelName },
      empty(modelVersion) ? {} : { version: modelVersion }
    )
  }
}

resource maps 'Microsoft.Maps/accounts@2023-06-01' = {
  name: '${prefix}-maps-${token}'
  location: 'global'
  tags: tags
  kind: 'Gen2'
  sku: { name: 'G2' }
  properties: {
    disableLocalAuth: true
  }
}

resource acrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, roles.acrPull)
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.acrPull)
  }
}

resource openAiUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(ai.id, identity.id, roles.openAiUser)
  scope: ai
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.openAiUser)
  }
}

resource mapsReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(maps.id, identity.id, roles.mapsDataReader)
  scope: maps
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.mapsDataReader)
  }
}

resource blobWriter 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableStorage) {
  name: guid(resourceGroup().id, identity.id, roles.blobContributor)
  scope: storage
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobContributor)
  }
}

resource env 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${prefix}-cae-${token}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

resource web 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${prefix}-web-${token}'
  location: location
  tags: union(tags, { 'azd-service-name': 'web' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: concat([
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'AZURE_AI_ENDPOINT', value: 'https://${aiSubdomain}.openai.azure.com/' }
            { name: 'AZURE_AI_DEPLOYMENT', value: model.name }
            { name: 'AZURE_MAPS_CLIENT_ID', value: maps.properties.uniqueId }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: insights.properties.ConnectionString }
          ], storageEnv)
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
  dependsOn: [acrPull]
}

output registryLoginServer string = registry.properties.loginServer
output registryName string = registry.name
output environmentId string = env.id
output environmentName string = env.name
output aiEndpoint string = 'https://${aiSubdomain}.openai.azure.com/'
output aiDeployment string = model.name
output mapsClientId string = maps.properties.uniqueId
output storageAccountUrl string = storage.?properties.primaryEndpoints.blob ?? ''
output webUri string = 'https://${web.properties.configuration.ingress.fqdn}'
