# Links every skill in this repo into ~/.claude/skills, where Claude Code looks for skills.
# Uses directory junctions, so no admin rights are needed. Run it again after a pull that
# adds, moves or renames a skill.
param([string]$Target = (Join-Path $HOME '.claude\skills'))

$repo = (Resolve-Path $PSScriptRoot).Path.TrimEnd('\')
if ($repo -ieq [IO.Path]::GetFullPath($Target).TrimEnd('\')) {
    throw "This clone is the skills folder itself. Move it elsewhere (for example ~/.claude/claude-skills) and run this again."
}
New-Item -ItemType Directory -Force $Target | Out-Null

# Remove links into this repo whose skill has moved or gone.
Get-ChildItem $Target -Directory -Force | Where-Object { $_.LinkType } | ForEach-Object {
    if ("$($_.Target)" -like "$repo\*" -and -not (Test-Path (Join-Path $_.FullName 'SKILL.md'))) {
        [IO.Directory]::Delete($_.FullName)
        "removed stale link $($_.Name)"
    }
}

$count = 0
Get-ChildItem $repo -Directory | Where-Object { $_.Name -notlike '.*' } | ForEach-Object {
    Get-ChildItem $_.FullName -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'SKILL.md') } | ForEach-Object {
        $link = Join-Path $Target $_.Name
        $existing = Get-Item $link -Force -ErrorAction SilentlyContinue
        if ($existing -and -not $existing.LinkType) {
            Write-Warning "skipped $($_.Name): $link is a real folder"
            return
        }
        if ($existing) { [IO.Directory]::Delete($link) }
        New-Item -ItemType Junction -Path $link -Target $_.FullName | Out-Null
        $count++
    }
}
"linked $count skills into $Target"
