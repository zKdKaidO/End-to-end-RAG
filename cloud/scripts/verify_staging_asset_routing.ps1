param(
    [string]$Origin = "https://staging.zkd.id.vn"
)

$ErrorActionPreference = "Stop"

function Invoke-Route {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [hashtable]$Headers = @{}
    )

    $handler = [System.Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $client = [System.Net.Http.HttpClient]::new($handler)
    try {
        $request = [System.Net.Http.HttpRequestMessage]::new([System.Net.Http.HttpMethod]::Get, "$Origin$Path")
        foreach ($header in $Headers.GetEnumerator()) {
            [void]$request.Headers.TryAddWithoutValidation($header.Key, [string]$header.Value)
        }
        $response = $client.SendAsync($request).GetAwaiter().GetResult()
        return [PSCustomObject]@{
            Status = [int]$response.StatusCode
            ContentType = $response.Content.Headers.ContentType.MediaType
            Location = if ($response.Headers.Location) { $response.Headers.Location.OriginalString } else { $null }
            Body = $response.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        }
    } finally {
        $client.Dispose()
        $handler.Dispose()
    }
}

function Assert-Route {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) { throw "Routing acceptance failed: $Message" }
}

$browserHeaders = @{
    Accept = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    "Sec-Fetch-Mode" = "navigate"
    "Sec-Fetch-Dest" = "document"
    "Sec-Fetch-Site" = "same-origin"
    "Upgrade-Insecure-Requests" = "1"
    "User-Agent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/152 Safari/537.36"
}

$oauthBrowser = Invoke-Route "/api/v1/auth/google/start" $browserHeaders
Assert-Route ($oauthBrowser.Status -eq 302) "browser OAuth start returned $($oauthBrowser.Status), not 302"
Assert-Route ($oauthBrowser.Location -like "https://accounts.google.com/*") "browser OAuth start did not redirect to Google"

$oauthNormal = Invoke-Route "/api/v1/auth/google/start"
Assert-Route ($oauthNormal.Status -eq 302 -and $oauthNormal.Location -like "https://accounts.google.com/*") "normal OAuth start did not redirect to Google"

$callback = Invoke-Route "/api/v1/auth/google/callback?code=invalid&state=invalid" $browserHeaders
Assert-Route ($callback.Status -eq 302 -and $callback.Location -like "/?auth_error=*") "OAuth callback did not execute Worker failure handling"

$me = Invoke-Route "/api/v1/auth/me" $browserHeaders
Assert-Route ($me.Status -eq 401 -and $me.ContentType -eq "application/json") "unauthenticated /api/v1/auth/me was not a JSON 401"

$unknownApi = Invoke-Route "/api/does-not-exist" $browserHeaders
Assert-Route ($unknownApi.Status -eq 404 -and $unknownApi.ContentType -eq "application/json") "unknown API route fell back to the SPA"

$root = Invoke-Route "/"
Assert-Route ($root.Status -eq 200 -and $root.ContentType -eq "text/html" -and $root.Body -match '<div id="root">') "root did not serve the SPA shell"

$spa = Invoke-Route "/documents"
Assert-Route ($spa.Status -eq 200 -and $spa.ContentType -eq "text/html" -and $spa.Body -match '<div id="root">') "SPA route did not serve the SPA shell"

$assetMatch = [regex]::Match($root.Body, 'src="(?<path>/assets/index-[^"]+\.js)"')
Assert-Route $assetMatch.Success "SPA shell did not reference a hashed JavaScript asset"
$asset = Invoke-Route $assetMatch.Groups["path"].Value
Assert-Route ($asset.Status -eq 200 -and $asset.ContentType -match "javascript") "hashed JavaScript asset was not served directly"

[PSCustomObject]@{
    oauth_browser = $oauthBrowser.Status
    oauth_normal = $oauthNormal.Status
    callback = $callback.Status
    auth_me = $me.Status
    unknown_api = $unknownApi.Status
    root = $root.Status
    spa = $spa.Status
    asset = $asset.Status
    asset_path = $assetMatch.Groups["path"].Value
} | ConvertTo-Json -Compress
