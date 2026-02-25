param(
    [switch]$SkipLogin = $false
)

$kvName = "kv-ps-bdo-dx-holmesdev"
$frontendEnvFile = "frontend/.env"
$backendEnvFile = "backend/.env"
$targetSubscriptionId = "377f1c95-4cf5-4c86-8bf4-6a274695a8cc"  # PS-BDO-DX-2-Prod

# Function to check if az command is available
function Test-AzCli {
    try {
        $null = & az --version 2>$null
        return $true
    }
    catch {
        return $false
    }
}

# Function to install Azure CLI
function Install-AzCli {
    Write-Host "Azure CLI not found. Attempting to install..."
    Write-Host ""
    Write-Host "This will install Azure CLI using winget. (Requires Admin rights)"
    $confirm = Read-Host "Continue with installation? (Y/N)"
    
    if ($confirm -ne "Y" -and $confirm -ne "y") {
        Write-Host "Installation cancelled."
        return $false
    }

    # Try using winget (built-in on Windows 11)
    try {
        Write-Host "Installing Azure CLI using winget..."

        winget install `
            --exact `
            --id Microsoft.AzureCLI `
            --source winget `
            --accept-package-agreements `
            --accept-source-agreements

        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("Path","User")

        # Verify installation
        if (Get-Command az -ErrorAction SilentlyContinue) {
            Write-Host "Azure CLI installed successfully."
            return $true
        } else {
            Write-Warning "Installation completed but 'az' not found in PATH."
            return $false
        }
    }
    catch {
        Write-Warning "Failed to install Azure CLI via winget: $_"
        return $false
    }
}

function Configure-Proxy {
    $proxy = "http://localhost:3128"

    Write-Host "Configuring proxy settings..."

    # Check if proxy is listening on port 3128
    $proxyRunning = $false
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.Connect("localhost", 3128)
        $tcpClient.Close()
        $proxyRunning = $true
    }
    catch {
        $proxyRunning = $false
    }

    if (-not $proxyRunning) {
        Write-Warning "No proxy detected on port 3128!"
        Write-Host ""
        Write-Host "You need to be running a proxy client. Recommended option:"
        Write-Host "  - GoNTLM: https://inside-docupedia.bosch.com/confluence/spaces/DEVCORNER/pages/2431652890/GoNTLM"
        Write-Host "    (preferred alternative to RB Local Proxy Manager)"
        Write-Host ""
        Write-Error "Please start your proxy client and try again."
        exit 1
    }

    # Current session
    $env:HTTP_PROXY  = $proxy
    $env:HTTPS_PROXY = $proxy
    $env:http_proxy  = $proxy
    $env:https_proxy = $proxy

    # Persist for current user (no admin required)
    [Environment]::SetEnvironmentVariable("HTTP_PROXY",  $proxy, "User")
    [Environment]::SetEnvironmentVariable("HTTPS_PROXY", $proxy, "User")
    [Environment]::SetEnvironmentVariable("http_proxy",  $proxy, "User")
    [Environment]::SetEnvironmentVariable("https_proxy", $proxy, "User")

    Write-Host "Proxy configured:"
    Write-Host "  $proxy"
}

function Configure-AzureCliRootCA {
    $certName = "RB RootCA RSA G01"
    $exportPath = "$env:LOCALAPPDATA\GlobalSign_Root_CA.cer"
    $mergedBundle = "$env:LOCALAPPDATA\azure_cli_cert.pem"

    Write-Host "Configuring Azure CLI custom Root CA..."

    # Locate certifi bundle used by Azure CLI
    $azPath = (Get-Command az).Source
    $azDir = Split-Path $azPath -Parent
    $azRoot = Split-Path $azDir -Parent
    $certifiBundle = Join-Path $azRoot "Lib\site-packages\certifi\cacert.pem"

    if (-not (Test-Path $certifiBundle)) {
        Write-Warning "Could not locate certifi bundle at expected path: $certifiBundle"
        return
    }

    # Find certificate in LocalMachine Root store
    $cert = Get-ChildItem Cert:\LocalMachine\Root, Cert:\CurrentUser\Root |
        Where-Object { $_.Subject -like "*$certName*" } |
        Select-Object -First 1

    if (-not $cert) {
        Write-Warning "Root CA '$certName' not found in LocalMachine\Root"
        return
    }

    # Export certificate to CER format first
    Export-Certificate -Cert $cert -FilePath $exportPath -Type CERT -Force | Out-Null

    # Convert CER to PEM format
    $certContent = [Convert]::ToBase64String([System.IO.File]::ReadAllBytes($exportPath), [System.Base64FormattingOptions]::InsertLineBreaks)
    $customCertPem = "-----BEGIN CERTIFICATE-----`r`n$certContent`r`n-----END CERTIFICATE-----"

    # Create merged bundle if missing or outdated
    Write-Host "Creating merged certificate bundle..."
    
    # Read the original certifi bundle and append our custom cert
    $bundleContent = Get-Content $certifiBundle -Raw
    $mergedContent = $bundleContent + "`r`n" + $customCertPem
    
    Set-Content -Path $mergedBundle -Value $mergedContent -NoNewline

    # Set environment variable (User level)
    [Environment]::SetEnvironmentVariable(
        "REQUESTS_CA_BUNDLE",
        $mergedBundle,
        "User"
    )

    # Also set for current session
    $env:REQUESTS_CA_BUNDLE = $mergedBundle

    Write-Host "Azure CLI Root CA configured."
}

# Check and install Azure CLI if needed
if (-not (Test-AzCli)) {
    if (-not (Install-AzCli)) {
        Write-Error "Failed to install Azure CLI. Please install it manually from https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows"
        exit 1
    }
    
    # Verify installation
    if (-not (Test-AzCli)) {
        Write-Error "Azure CLI installation verification failed. Please restart PowerShell and try again."
        exit 1
    }
}

Write-Host "Azure CLI is ready"

Configure-Proxy
Configure-AzureCliRootCA

# Make sure you're logged in (unless skipped)
if (-not $SkipLogin) {
    Write-Host "Logging into Azure..."
    az login
    
    Write-Host "Setting subscription to PS-BDO-DX-2-Prod..."
    az account set --subscription $targetSubscriptionId
    
    if ($?) {
        Write-Host "Subscription set successfully"
    }
    else {
        Write-Error "Failed to set subscription"
        exit 1
    }
}

# Clear or create the files
foreach ($envFile in @($frontendEnvFile, $backendEnvFile)) {
    $dir = Split-Path -Parent $envFile
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    
    if (Test-Path $envFile) {
        Clear-Content $envFile
    } else {
        New-Item $envFile -ItemType File | Out-Null
    }
}

# Get all secret names
try {
    $secrets = az keyvault secret list `
        --vault-name $kvName `
        --query "[].name" -o tsv
    
    if (-not $secrets) {
        Write-Error "No secrets found in Key Vault '$kvName'. Check vault name and permissions."
        exit 1
    }
    
    foreach ($name in $secrets) {
        # Get secret value and tags
        $secretData = az keyvault secret show `
            --vault-name $kvName `
            --name $name `
            --query "{value: value, tags: tags}" -o json | ConvertFrom-Json
        
        $value = $secretData.value
        $tags = $secretData.tags
        
        # Determine which environments this secret should be added to
        $addToFrontend = $false
        $addToBackend = $false
        
        if ($tags) {
            if ($tags.PSObject.Properties["frontend"] -and $tags.frontend -eq "true") {
                $addToFrontend = $true
            }
            if ($tags.PSObject.Properties["backend"] -and $tags.backend -eq "true") {
                $addToBackend = $true
            }
        }
        
        # If no tags, skip the secret (or optionally add to both)
        if (-not ($addToFrontend -or $addToBackend)) {
            Write-Warning "Secret '$name' has no applicable tags (frontend or backend not set to true). Skipping."
            continue
        }
        
        # Replace hyphens with underscores in key name
        $normalizedName = $name -replace "-", "_"
        
        # Add to frontend .env if applicable
        if ($addToFrontend) {
            Add-Content $frontendEnvFile "$normalizedName=$value"
        }
        
        # Add to backend .env if applicable
        if ($addToBackend) {
            Add-Content $backendEnvFile "$normalizedName=$value"
        }
    }

    Write-Host "Secrets exported successfully!"
    Write-Host "  - Frontend: $frontendEnvFile"
    Write-Host "  - Backend: $backendEnvFile"
}
catch {
    Write-Error "Failed to retrieve secrets from Key Vault: $_"
    Write-Host "Make sure you are logged in with az login and have access to the vault."
    exit 1
}