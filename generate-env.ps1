param(
    [switch]$SkipLogin = $false
)

$kvName = "kv-ps-bdo-dx-holmesdev"
$outputFile = ".env"
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
    
    # Try using winget (built-in on Windows 11)
    try {
        Write-Host "Installing Azure CLI using winget..."
        & winget install Microsoft.AzureCLI -e -h --accept-source-agreements | Out-Null
        Write-Host "Azure CLI installed successfully via winget"
        
        # Refresh PATH to make az available
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        return $true
    }
    catch {
        Write-Warning "Failed to install Azure CLI via winget: $_"
    }
    
    # Fallback: Try using Chocolatey
    try {
        Write-Host "Attempting to install Azure CLI using Chocolatey..."
        & choco install azure-cli -y | Out-Null
        Write-Host "Azure CLI installed successfully via Chocolatey"
        
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        return $true
    }
    catch {
        Write-Warning "Failed to install Azure CLI via Chocolatey: $_"
    }
    
    # Fallback: Direct download from Microsoft
    try {
        Write-Host "Attempting to install Azure CLI from Microsoft..."
        $url = "https://aka.ms/installazurecliwindows"
        $installer = "$env:TEMP\AzureCLI.msi"
        
        Write-Host "Downloading Azure CLI installer..."
        Invoke-WebRequest -Uri $url -OutFile $installer -ErrorAction Stop
        
        Write-Host "Running installer..."
        Start-Process msiexec.exe -ArgumentList "/i `"$installer`" /quiet" -Wait
        
        Remove-Item $installer -Force -ErrorAction SilentlyContinue
        
        # Refresh PATH
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        
        Write-Host "Azure CLI installed successfully from Microsoft"
        return $true
    }
    catch {
        Write-Error "Failed to install Azure CLI from Microsoft: $_"
        return $false
    }
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

# Clear or create the file
if (Test-Path $outputFile) {
    Clear-Content $outputFile
} else {
    New-Item $outputFile -ItemType File | Out-Null
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
        $value = az keyvault secret show `
            --vault-name $kvName `
            --name $name `
            --query "value" -o tsv

        Add-Content $outputFile "$name=$value"
    }

    Write-Host "Exported secrets to $outputFile"
}
catch {
    Write-Error "Failed to retrieve secrets from Key Vault: $_"
    Write-Host "Make sure you're logged in with 'az login' and have access to the vault."
    exit 1
}