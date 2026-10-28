# Native PowerShell 5.1+ TOML statement editor. No external runtime.
$Sep = [string][char]28
$DiscoveryKey = 'features' + $Sep + 'api_key_model_discovery'
function New-ConfigMap { return [Collections.Specialized.OrderedDictionary]::new([StringComparer]::Ordinal) }
$Fields = New-ConfigMap
$Tables = New-ConfigMap
$Headers = New-ConfigMap
$Records = [Collections.Generic.List[object]]::new()
$Providers = New-ConfigMap
$Removed = New-ConfigMap
$State = @{ Active = ''; Selected = ''; Discovery = '' }
function Stop-ConfigEdit([string]$Message) { throw ('Codex config unchanged: ' + $Message) }
function Split-ConfigParts([string]$Text, [string]$Delimiter, [bool]$Clean = $false) {
    $parts = [Collections.Generic.List[string]]::new()
    $piece = [Text.StringBuilder]::new()
    $quote = ''; $stack = ''; $comment = $false
    for ($i=0; $i -lt $Text.Length; $i++) {
        $c = [string]$Text[$i]
        if ($comment) {
            if ($c -ne [string][char]10) { if (-not $Clean) { [void]$piece.Append($c) }; continue }
            $comment = $false
        }
        if ($quote) {
            [void]$piece.Append($c)
            if ($quote.StartsWith('"') -and $c -eq '\') { $i++; if ($i -lt $Text.Length) { [void]$piece.Append($Text[$i]) }; continue }
            if ($quote.Length -eq 1 -and $c -eq [string][char]10) { Stop-ConfigEdit 'newline in a single-line string' }
            if ($quote.Length -eq 1 -and $c -eq $quote) { $quote = '' }
            elseif ($quote.Length -eq 3 -and $Text.Substring($i).StartsWith($quote)) {
                $run = 3
                while (($i+$run) -lt $Text.Length -and [string]$Text[$i+$run] -eq $c -and $run -lt 5) { $run++ }
                [void]$piece.Append($Text.Substring($i+1,$run-1)); $i += $run-1; $quote = ''
            }
            continue
        }
        if ($c -eq '#') { $comment=$true; if (-not $Clean) { [void]$piece.Append($c) }; continue }
        if ($c -eq '"' -or $c -eq "'") {
            $quote=$c
            if ($Text.Substring($i).StartsWith($c+$c+$c)) { $quote=$c+$c+$c; [void]$piece.Append($quote); $i+=2 }
            else { [void]$piece.Append($c) }
            continue
        }
        if ($c -eq '[' -or $c -eq '{') { $stack += $c }
        if ($c -eq ']' -or $c -eq '}') {
            $expected = if ($c -eq ']') { '[' } else { '{' }
            if (-not $stack -or [string]$stack[$stack.Length-1] -ne $expected) { Stop-ConfigEdit 'unbalanced brackets' }
            $stack = $stack.Substring(0,$stack.Length-1)
        }
        if ($Delimiter -and $c -eq $Delimiter -and -not $stack) { $parts.Add($piece.ToString()); [void]$piece.Clear() }
        else { [void]$piece.Append($c) }
    }
    if ($quote -or $stack) { Stop-ConfigEdit 'unterminated string or table' }
    $parts.Add($piece.ToString())
    return ,$parts.ToArray()
}
function Get-ConfigCode([string]$Text) { return (Split-ConfigParts $Text '' $true)[0].Trim() }
function Read-ConfigString([string]$Value) {
    $Value=$Value.Trim()
    if (-not $Value -or ([string]$Value[0] -ne '"' -and [string]$Value[0] -ne "'")) { return '' }
    $q=[string]$Value[0]
    if (-not $Value.EndsWith($q)) { Stop-ConfigEdit 'invalid quoted value' }
    if ($Value.StartsWith($q+$q+$q)) { $Value=$Value.Substring(3,$Value.Length-6) } else { $Value=$Value.Substring(1,$Value.Length-2) }
    if ($q -eq "'") { return $Value }
    $result=[Text.StringBuilder]::new()
    for($i=0;$i -lt $Value.Length;$i++) {
        $c=[string]$Value[$i]
        if($c -ne '\') { [void]$result.Append($c); continue }
        $i++; if($i -ge $Value.Length) { Stop-ConfigEdit 'invalid string escape' }; $e=[string]$Value[$i]
        switch -CaseSensitive ($e) {
            'u' { $point=[Convert]::ToInt32($Value.Substring($i+1,4),16); [void]$result.Append([char]::ConvertFromUtf32($point)); $i+=4 }
            'U' { $point=[Convert]::ToInt32($Value.Substring($i+1,8),16); [void]$result.Append([char]::ConvertFromUtf32($point)); $i+=8 }
            'n' { [void]$result.Append([char]10) }
            'r' { [void]$result.Append([char]13) }
            't' { [void]$result.Append([char]9) }
            'b' { [void]$result.Append([char]8) }
            'f' { [void]$result.Append([char]12) }
            '\' { [void]$result.Append('\') }
            '"' { [void]$result.Append('"') }
            default { Stop-ConfigEdit 'unsupported string escape' }
        }
    }
    return $result.ToString()
}
function Get-ConfigPath([string]$Text) {
    $keys=[Collections.Generic.List[string]]::new()
    foreach($part in (Split-ConfigParts $Text '.')) {
        $k=$part.Trim()
        if($k -cnotmatch '^[A-Za-z0-9_-]+$') {
            if(-not $k -or ([string]$k[0] -ne '"' -and [string]$k[0] -ne "'")) { Stop-ConfigEdit 'invalid key' }
            $k=Read-ConfigString $k
        }
        if($k.Contains($Sep)) { Stop-ConfigEdit 'unsupported control character in key' }
        $keys.Add($k)
    }
    return [string]::Join($Sep,$keys)
}
function Quote-ConfigString([string]$Value) { return '"' + $Value.Replace('\','\\').Replace('"','\"').Replace([string][char]10,'\n').Replace([string][char]13,'\r').Replace([string][char]9,'\t') + '"' }
function Format-ConfigKey([string]$Value) { if($Value -cmatch '^[A-Za-z0-9_-]+$') { return $Value }; return Quote-ConfigString $Value }
function Format-ConfigPath([string]$Value) { return (($Value.Split([char]28) | ForEach-Object { Format-ConfigKey $_ }) -join '.') }
function Test-ManagedPath([string]$Path) { return $Path -ceq 'features' -or $Path.StartsWith('features'+$Sep) -or $Path -ceq 'model_providers' -or $Path.StartsWith('model_providers'+$Sep) }
function Get-ConfigField([string]$Path) { if($Fields.Contains($Path)) { return [string]$Fields[$Path] }; return '' }
function Add-ConfigValue([string]$Path,[string]$Value) {
    $Value=$Value.Trim()
    if(-not $Value) { Stop-ConfigEdit 'missing value' }
    if($Value.StartsWith('{')) {
        if(-not $Value.EndsWith('}')) { Stop-ConfigEdit 'invalid inline table' }
        $Tables[$Path]=$true; $Value=$Value.Substring(1,$Value.Length-2)
        if(-not $Value.Trim()) { return }
        foreach($part in (Split-ConfigParts $Value ',')) {
            $pair=Split-ConfigParts $part '='
            if($pair.Count -ne 2) { Stop-ConfigEdit 'invalid inline table field' }
            Add-ConfigValue ($Path+$Sep+(Get-ConfigPath $pair[0])) $pair[1]
        }
    } else {
        if($Fields.Contains($Path)) { Stop-ConfigEdit 'duplicate setting' }
        if($Path -ceq 'features' -or $Path -ceq 'model_providers' -or ($Path.StartsWith('model_providers'+$Sep) -and $Path.Split([char]28).Count -lt 3)) { Stop-ConfigEdit 'expected a table' }
        $Fields[$Path]=$Value
    }
}
function Read-ConfigDocument([string]$Text) {
    $section=''
    foreach($raw in (Split-ConfigParts $Text ([string][char]10))) {
        $value=Get-ConfigCode $raw
        if(-not $value) { if($raw.Trim() -or -not (Test-ManagedPath $section)) { $Records.Add(@{text=$raw;path='';value=''}) }; continue }
        if($value.StartsWith('[')) {
            $arrayTable=$value.StartsWith('[['); $width=if($arrayTable){2}else{1}
            $section=Get-ConfigPath ($value.Substring($width,$value.Length-2*$width))
            if(Test-ManagedPath $section) {
                if($arrayTable) { Stop-ConfigEdit 'provider/feature array tables are not supported' }
                if($Headers.Contains($section)) { Stop-ConfigEdit 'duplicate table' }
                $Headers[$section]=$true; $Tables[$section]=$true
            } else { $Records.Add(@{text=$raw;path='';value=''}) }
            continue
        }
        $pair=Split-ConfigParts $value '='
        if($pair.Count -ne 2) { Stop-ConfigEdit 'invalid setting' }
        $p=Get-ConfigPath $pair[0]; if($section) { $p=$section+$Sep+$p }
        if(Test-ManagedPath $p) {
            Add-ConfigValue $p $pair[1]
            if($p -ceq $DiscoveryKey -and $raw -cmatch '# codex-lb-feature-(owned|was-false)[ \t]*$') { $State.Discovery=$Matches[1] }
        } else {
            $Records.Add(@{text=$raw;path=$p;value=$pair[1].Trim()})
            if($p -ceq 'model_provider') { $State.Active=Read-ConfigString $pair[1] }
        }
    }
}
function Remove-ConfigPrefix([string]$Prefix) {
    foreach($p in @($Fields.Keys)) { if($p -ceq $Prefix -or $p.StartsWith($Prefix+$Sep)) { $Fields.Remove($p) } }
    foreach($p in @($Tables.Keys)) { if($p -ceq $Prefix -or $p.StartsWith($Prefix+$Sep)) { $Tables.Remove($p) } }
}
function Test-RelayProvider([string]$Id) {
    $prefix='model_providers'+$Sep+$Id
    $url=(Read-ConfigString (Get-ConfigField ($prefix+$Sep+'base_url'))).TrimEnd('/')
    $token=Read-ConfigString (Get-ConfigField ($prefix+$Sep+'experimental_bearer_token'))
    if($url -and $url -ceq $RelaySettings.base_url) { return $true }
    if($url.EndsWith('/backend-api/codex') -and $token.StartsWith('sk-clb-')) { return $true }
    if($url.EndsWith('/backend-api/codex')) {
        foreach($p in $Fields.Keys) { if($p.StartsWith($prefix+$Sep+'auth'+$Sep) -and $Fields[$p].Contains('codex-lb.key')) { return $true } }
    }
    foreach($p in $Fields.Keys) {
        $a=$p.Split([char]28)
        if($a.Count -eq 4 -and $a[0] -ceq 'model_providers' -and $a[1] -ceq $Id -and $a[2] -ceq 'http_headers' -and $a[3] -ieq 'x-openai-actor-authorization' -and (Read-ConfigString $Fields[$p]) -ceq 'codex-lb') { return $true }
    }
    return $false
}
function Set-RelayConfiguration {
    $custom=@($Providers.Keys | Where-Object { $_ -cnotin @('openai','ollama','lmstudio') })
    if($Providers.Contains($State.Active) -and $State.Active -cnotin @('openai','ollama','lmstudio')) { $State.Selected=$State.Active }
    elseif($Providers.Contains('openai_https')) { $State.Selected='openai_https' }
    elseif($custom.Count -eq 1) { $State.Selected=$custom[0] } else { $State.Selected='openai_https' }
    $prefix='model_providers'+$Sep+$State.Selected
    Remove-ConfigPrefix ($prefix+$Sep+'auth')
    $Fields.Remove($prefix+$Sep+'env_key'); $Fields.Remove($prefix+$Sep+'env_key_instructions')
    foreach($p in @($Fields.Keys)) {
        $a=$p.Split([char]28)
        if($a.Count -eq 4 -and $a[0] -ceq 'model_providers' -and $a[1] -ceq $State.Selected -and $a[2] -cin @('http_headers','env_http_headers') -and $a[3] -iin @('authorization','x-openai-actor-authorization')) {
            if($a[2] -ceq 'http_headers' -and $a[3] -ceq 'x-openai-actor-authorization') { continue }
            $Fields.Remove($p)
        }
    }
    $Fields[$prefix+$Sep+'name']='"OpenAI"'; $Fields[$prefix+$Sep+'base_url']=$RelaySettings.base_value
    $Fields[$prefix+$Sep+'model_catalog_url']=$RelaySettings.catalog_value; $Fields[$prefix+$Sep+'wire_api']='"responses"'
    $Fields[$prefix+$Sep+'experimental_bearer_token']=$RelaySettings.token_value; $Fields[$prefix+$Sep+'requires_openai_auth']='true'
    $Fields[$prefix+$Sep+'http_headers'+$Sep+'x-openai-actor-authorization']='"codex-lb"'
    $Fields[$prefix+$Sep+'supports_websockets']='false'
    if(-not $State.Discovery) {
        if(-not $Fields.Contains($DiscoveryKey)) { $State.Discovery='owned' }
        elseif($Fields[$DiscoveryKey] -ceq 'false') { $State.Discovery='was-false' }
    }
    $Fields[$DiscoveryKey]='true'
}
function Remove-RelayConfiguration {
    foreach($id in $Providers.Keys) {
        if(-not (Test-RelayProvider $id)) { continue }
        $Removed[$id]=$true; $prefix='model_providers'+$Sep+$id
        foreach($p in @($Fields.Keys)) {
            if($p.StartsWith($prefix+$Sep+'auth'+$Sep) -and $Fields[$p].Contains('codex-lb.key')) { Remove-ConfigPrefix ($prefix+$Sep+'auth'); break }
        }
        foreach($field in @('base_url','model_catalog_url','experimental_bearer_token','requires_openai_auth','wire_api','supports_websockets')) { $Fields.Remove($prefix+$Sep+$field) }
        foreach($p in @($Fields.Keys)) {
            $a=$p.Split([char]28)
            if($a.Count -eq 4 -and $a[0] -ceq 'model_providers' -and $a[1] -ceq $id -and $a[2] -ceq 'http_headers' -and $a[3] -ieq 'x-openai-actor-authorization' -and (Read-ConfigString $Fields[$p]) -ceq 'codex-lb') { $Fields.Remove($p) }
        }
        $remaining=@($Fields.Keys | Where-Object { $_.StartsWith($prefix+$Sep) -and $_ -cne ($prefix+$Sep+'name') })
        $remaining+=@($Tables.Keys | Where-Object { $_.StartsWith($prefix+$Sep) -and $_ -cnotin @(($prefix+$Sep+'http_headers'),($prefix+$Sep+'env_http_headers')) })
        if($remaining.Count -eq 0) { Remove-ConfigPrefix $prefix }
    }
    if($Removed.Count -gt 0 -and $State.Discovery -ceq 'owned') { $Fields.Remove($DiscoveryKey); $State.Discovery='' }
    elseif($Removed.Count -gt 0 -and $State.Discovery -ceq 'was-false') { $Fields[$DiscoveryKey]='false'; $State.Discovery='' }
}
function Write-ConfigDocument {
    if($RelaySettings.mode -ceq 'cleanup' -and $Removed.Count -eq 0) { return $Original }
    $lines=[Collections.Generic.List[string]]::new()
    foreach($record in $Records) {
        if($RelaySettings.mode -ceq 'setup' -and $record.path -cin @('model','model_provider')) { continue }
        $a=$record.path.Split([char]28)
        if($RelaySettings.mode -ceq 'cleanup' -and ($record.path -ceq 'model_provider' -or ($a.Count -eq 3 -and $a[0] -ceq 'profiles' -and $a[2] -ceq 'model_provider')) -and $Removed.Contains((Read-ConfigString $record.value))) { continue }
        $lines.Add($record.text)
    }
    $lf=[string][char]10
    $result=([string]::Join($lf,$lines)).Trim([char]10)
    if($RelaySettings.mode -ceq 'setup') { $result='model = '+$RelaySettings.model_value+$lf+'model_provider = '+(Quote-ConfigString $State.Selected)+$lf+$lf+$result }
    $result=$result.TrimEnd([char]10)
    $groups=New-ConfigMap
    foreach($p in $Fields.Keys) { $group=$p.Substring(0,$p.LastIndexOf($Sep)); $groups[$group]=$true }
    foreach($p in $Tables.Keys) {
        if($groups.Contains($p)) { continue }
        $children=@($Fields.Keys | Where-Object { $_.StartsWith($p+$Sep) })
        $a=$p.Split([char]28)
        if($children.Count -eq 0) { $groups[$p]=$true }
    }
    foreach($group in $groups.Keys) {
        $result+=$lf+$lf+'['+(Format-ConfigPath $group)+']'+$lf
        foreach($p in $Fields.Keys) {
            if($p.Substring(0,$p.LastIndexOf($Sep)) -cne $group) { continue }
            $result+=(Format-ConfigKey ($p.Substring($p.LastIndexOf($Sep)+1)))+' = '+$Fields[$p]
            if($p -ceq $DiscoveryKey -and $State.Discovery) { $result+=' # codex-lb-feature-'+$State.Discovery }
            $result+=$lf
        }
        $result=$result.TrimEnd([char]10)
    }
    $result=$result.Trim([char]10)
    if($result) { $result+=$lf }
    return $result
}
Read-ConfigDocument ($Original.Replace(([string][char]13+[char]10),[string][char]10))
foreach($p in @($Fields.Keys)+@($Tables.Keys)) {
    $a=$p.Split([char]28)
    if($a.Count -ge 2 -and $a[0] -ceq 'model_providers') { $Providers[$a[1]]=$true }
}
if($RelaySettings.mode -ceq 'setup') { Set-RelayConfiguration } else { Remove-RelayConfiguration }
$Updated=Write-ConfigDocument
