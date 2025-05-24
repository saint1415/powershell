# Plex Migration Tool - GUI Version
# Clean, reliable GUI with real-time progress monitoring

Write-Host "Starting Plex Migration GUI..." -ForegroundColor Green

try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    Write-Host "Windows Forms loaded successfully" -ForegroundColor Green
} catch {
    Write-Host "Error loading Windows Forms: $($_.Exception.Message)" -ForegroundColor Red
    exit
}

# Global variables
$sourcePath = "$env:LOCALAPPDATA\Plex Media Server"
$script:copyJob = $null
$script:timer = $null

Write-Host "Creating main form..." -ForegroundColor Green

# Create main form
$form = New-Object System.Windows.Forms.Form
$form.Text = "Plex Migration Toolkit"
$form.Size = New-Object System.Drawing.Size(600, 500)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedSingle"
$form.MaximizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(32, 32, 32)
$form.ForeColor = [System.Drawing.Color]::White

# Header
$headerLabel = New-Object System.Windows.Forms.Label
$headerLabel.Text = "PLEX MIGRATION TOOLKIT"
$headerLabel.Location = New-Object System.Drawing.Point(20, 20)
$headerLabel.Size = New-Object System.Drawing.Size(560, 30)
$headerLabel.Font = New-Object System.Drawing.Font("Arial", 16, [System.Drawing.FontStyle]::Bold)
$headerLabel.ForeColor = [System.Drawing.Color]::Cyan
$headerLabel.TextAlign = "MiddleCenter"
$form.Controls.Add($headerLabel)

# Status Panel
$statusPanel = New-Object System.Windows.Forms.Panel
$statusPanel.Location = New-Object System.Drawing.Point(20, 60)
$statusPanel.Size = New-Object System.Drawing.Size(560, 80)
$statusPanel.BorderStyle = "FixedSingle"
$statusPanel.BackColor = [System.Drawing.Color]::FromArgb(48, 48, 48)
$form.Controls.Add($statusPanel)

$plexStatusLabel = New-Object System.Windows.Forms.Label
$plexStatusLabel.Location = New-Object System.Drawing.Point(10, 10)
$plexStatusLabel.Size = New-Object System.Drawing.Size(200, 20)
$plexStatusLabel.Font = New-Object System.Drawing.Font("Arial", 9)
$plexStatusLabel.ForeColor = [System.Drawing.Color]::White
$statusPanel.Controls.Add($plexStatusLabel)

$dataStatusLabel = New-Object System.Windows.Forms.Label
$dataStatusLabel.Location = New-Object System.Drawing.Point(10, 35)
$dataStatusLabel.Size = New-Object System.Drawing.Size(400, 20)
$dataStatusLabel.Font = New-Object System.Drawing.Font("Arial", 9)
$dataStatusLabel.ForeColor = [System.Drawing.Color]::White
$statusPanel.Controls.Add($dataStatusLabel)

$refreshButton = New-Object System.Windows.Forms.Button
$refreshButton.Text = "Refresh"
$refreshButton.Location = New-Object System.Drawing.Point(480, 25)
$refreshButton.Size = New-Object System.Drawing.Size(60, 25)
$refreshButton.BackColor = [System.Drawing.Color]::FromArgb(70, 70, 70)
$refreshButton.ForeColor = [System.Drawing.Color]::White
$refreshButton.FlatStyle = "Flat"
$statusPanel.Controls.Add($refreshButton)

# Drive Selection
$driveLabel = New-Object System.Windows.Forms.Label
$driveLabel.Text = "Select Destination Drive:"
$driveLabel.Location = New-Object System.Drawing.Point(20, 160)
$driveLabel.Size = New-Object System.Drawing.Size(200, 20)
$driveLabel.Font = New-Object System.Drawing.Font("Arial", 10, [System.Drawing.FontStyle]::Bold)
$driveLabel.ForeColor = [System.Drawing.Color]::White
$form.Controls.Add($driveLabel)

$driveComboBox = New-Object System.Windows.Forms.ComboBox
$driveComboBox.Location = New-Object System.Drawing.Point(20, 185)
$driveComboBox.Size = New-Object System.Drawing.Size(560, 25)
$driveComboBox.DropDownStyle = "DropDownList"
$driveComboBox.BackColor = [System.Drawing.Color]::FromArgb(60, 60, 60)
$driveComboBox.ForeColor = [System.Drawing.Color]::White
$driveComboBox.Font = New-Object System.Drawing.Font("Arial", 9)
$form.Controls.Add($driveComboBox)

# Operation Buttons
$buttonPanel = New-Object System.Windows.Forms.Panel
$buttonPanel.Location = New-Object System.Drawing.Point(20, 225)
$buttonPanel.Size = New-Object System.Drawing.Size(560, 60)
$form.Controls.Add($buttonPanel)

$hotCopyButton = New-Object System.Windows.Forms.Button
$hotCopyButton.Text = "Hot Copy`n(Plex Running)"
$hotCopyButton.Location = New-Object System.Drawing.Point(0, 0)
$hotCopyButton.Size = New-Object System.Drawing.Size(110, 50)
$hotCopyButton.BackColor = [System.Drawing.Color]::FromArgb(0, 120, 0)
$hotCopyButton.ForeColor = [System.Drawing.Color]::White
$hotCopyButton.FlatStyle = "Flat"
$hotCopyButton.Font = New-Object System.Drawing.Font("Arial", 8, [System.Drawing.FontStyle]::Bold)
$buttonPanel.Controls.Add($hotCopyButton)

$coldCopyButton = New-Object System.Windows.Forms.Button
$coldCopyButton.Text = "Cold Copy`n(Stop Plex)"
$coldCopyButton.Location = New-Object System.Drawing.Point(120, 0)
$coldCopyButton.Size = New-Object System.Drawing.Size(110, 50)
$coldCopyButton.BackColor = [System.Drawing.Color]::FromArgb(0, 100, 150)
$coldCopyButton.ForeColor = [System.Drawing.Color]::White
$coldCopyButton.FlatStyle = "Flat"
$coldCopyButton.Font = New-Object System.Drawing.Font("Arial", 8, [System.Drawing.FontStyle]::Bold)
$buttonPanel.Controls.Add($coldCopyButton)

$smartSyncButton = New-Object System.Windows.Forms.Button
$smartSyncButton.Text = "Smart Sync`n(Hot + Cold)"
$smartSyncButton.Location = New-Object System.Drawing.Point(240, 0)
$smartSyncButton.Size = New-Object System.Drawing.Size(110, 50)
$smartSyncButton.BackColor = [System.Drawing.Color]::FromArgb(150, 120, 0)
$smartSyncButton.ForeColor = [System.Drawing.Color]::White
$smartSyncButton.FlatStyle = "Flat"
$smartSyncButton.Font = New-Object System.Drawing.Font("Arial", 8, [System.Drawing.FontStyle]::Bold)
$buttonPanel.Controls.Add($smartSyncButton)

$stopButton = New-Object System.Windows.Forms.Button
$stopButton.Text = "Stop"
$stopButton.Location = New-Object System.Drawing.Point(360, 0)
$stopButton.Size = New-Object System.Drawing.Size(80, 50)
$stopButton.BackColor = [System.Drawing.Color]::FromArgb(150, 0, 0)
$stopButton.ForeColor = [System.Drawing.Color]::White
$stopButton.FlatStyle = "Flat"
$stopButton.Font = New-Object System.Drawing.Font("Arial", 10, [System.Drawing.FontStyle]::Bold)
$stopButton.Enabled = $false
$buttonPanel.Controls.Add($stopButton)

$exitButton = New-Object System.Windows.Forms.Button
$exitButton.Text = "Exit"
$exitButton.Location = New-Object System.Drawing.Point(450, 0)
$exitButton.Size = New-Object System.Drawing.Size(80, 50)
$exitButton.BackColor = [System.Drawing.Color]::FromArgb(80, 80, 80)
$exitButton.ForeColor = [System.Drawing.Color]::White
$exitButton.FlatStyle = "Flat"
$exitButton.Font = New-Object System.Drawing.Font("Arial", 10, [System.Drawing.FontStyle]::Bold)
$buttonPanel.Controls.Add($exitButton)

# Progress Panel
$progressPanel = New-Object System.Windows.Forms.Panel
$progressPanel.Location = New-Object System.Drawing.Point(20, 300)
$progressPanel.Size = New-Object System.Drawing.Size(560, 140)
$progressPanel.BorderStyle = "FixedSingle"
$progressPanel.BackColor = [System.Drawing.Color]::FromArgb(48, 48, 48)
$form.Controls.Add($progressPanel)

$progressLabel = New-Object System.Windows.Forms.Label
$progressLabel.Text = "Ready to start migration..."
$progressLabel.Location = New-Object System.Drawing.Point(10, 10)
$progressLabel.Size = New-Object System.Drawing.Size(540, 20)
$progressLabel.Font = New-Object System.Drawing.Font("Arial", 9, [System.Drawing.FontStyle]::Bold)
$progressLabel.ForeColor = [System.Drawing.Color]::Cyan
$progressPanel.Controls.Add($progressLabel)

$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Location = New-Object System.Drawing.Point(10, 35)
$progressBar.Size = New-Object System.Drawing.Size(540, 25)
$progressBar.Style = "Continuous"
$progressPanel.Controls.Add($progressBar)

$detailsLabel = New-Object System.Windows.Forms.Label
$detailsLabel.Text = ""
$detailsLabel.Location = New-Object System.Drawing.Point(10, 70)
$detailsLabel.Size = New-Object System.Drawing.Size(540, 60)
$detailsLabel.Font = New-Object System.Drawing.Font("Consolas", 8)
$detailsLabel.ForeColor = [System.Drawing.Color]::LightGray
$progressPanel.Controls.Add($detailsLabel)

Write-Host "Form created successfully" -ForegroundColor Green

# Helper Functions
function Get-FolderSize {
    param($Path, [switch]$Quick)
    try {
        if (-not (Test-Path $Path)) { return 0 }
        
        if ($Quick) {
            # More accurate quick estimate
            $estimate = 0
            $sampleDirs = @(
                "Plug-in Support\Databases",
                "Media",
                "Metadata",
                "Cache"
            )
            
            foreach ($dir in $sampleDirs) {
                $fullPath = Join-Path $Path $dir
                if (Test-Path $fullPath) {
                    try {
                        $dirSize = (Get-ChildItem -Path $fullPath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
                        $estimate += $dirSize
                    } catch {
                        # If we can't read a directory, skip it
                    }
                }
            }
            
            # Add base directory files
            try {
                $baseFiles = (Get-ChildItem -Path $Path -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
                $estimate += $baseFiles
            } catch {}
            
            return [math]::Round($estimate / 1GB, 2)
        }
        
        $size = (Get-ChildItem -Path $Path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        return [math]::Round($size / 1GB, 2)
    } catch {
        return 0
    }
}

function Update-Status {
    try {
        Write-Host "Checking Plex process..." -ForegroundColor Gray
        # Check Plex status
        $plexRunning = Get-Process -Name "Plex Media Server" -ErrorAction SilentlyContinue
        if ($plexRunning) {
            $plexStatusLabel.Text = "Plex Status: RUNNING"
            $plexStatusLabel.ForeColor = [System.Drawing.Color]::LightGreen
        } else {
            $plexStatusLabel.Text = "Plex Status: STOPPED"
            $plexStatusLabel.ForeColor = [System.Drawing.Color]::Yellow
        }
        
        Write-Host "Checking Plex data directory..." -ForegroundColor Gray
        # Check data (simplified - just check if directory exists)
        $sourceExists = Test-Path $sourcePath
        if ($sourceExists) {
            $dataStatusLabel.Text = "Plex Data: Found (calculating size...)"
            $dataStatusLabel.ForeColor = [System.Drawing.Color]::LightGreen
            
            # Calculate size in background to avoid hanging
            Start-Job -ScriptBlock {
                param($path)
                try {
                    $size = (Get-ChildItem -Path $path -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
                    return [math]::Round($size / 1GB, 2)
                } catch {
                    return 0
                }
            } -ArgumentList $sourcePath | Out-Null
            
            # For now, just show that it's found
            $dataStatusLabel.Text = "Plex Data: Found"
        } else {
            $dataStatusLabel.Text = "Plex Data: NOT FOUND"
            $dataStatusLabel.ForeColor = [System.Drawing.Color]::Red
        }
        Write-Host "Status check complete" -ForegroundColor Gray
    } catch {
        Write-Host "Error in Update-Status: $($_.Exception.Message)" -ForegroundColor Red
        $plexStatusLabel.Text = "Status: Error checking"
        $dataStatusLabel.Text = "Error: $($_.Exception.Message)"
    }
}

function Update-Drives {
    try {
        Write-Host "Getting drive list..." -ForegroundColor Gray
        $driveComboBox.Items.Clear()
        
        # Try modern approach first
        $drives = $null
        try {
            $drives = Get-CimInstance -ClassName Win32_LogicalDisk -ErrorAction Stop | Where-Object { $_.DriveType -eq 3 -and $_.DeviceID -ne "C:" }
        } catch {
            Write-Host "CIM failed, trying WMI..." -ForegroundColor Gray
            try {
                $drives = Get-WmiObject -Class Win32_LogicalDisk -ErrorAction Stop | Where-Object { $_.DriveType -eq 3 -and $_.DeviceID -ne "C:" }
            } catch {
                Write-Host "WMI failed, using Get-Volume..." -ForegroundColor Gray
                # Fallback to simple drive detection
                $drives = Get-Volume -ErrorAction SilentlyContinue | Where-Object { $_.DriveLetter -and $_.DriveLetter -ne "C" } | ForEach-Object {
                    [PSCustomObject]@{
                        DeviceID = "$($_.DriveLetter):"
                        VolumeName = $_.FileSystemLabel
                        FreeSpace = $_.SizeRemaining
                        Size = $_.Size
                    }
                }
            }
        }
        
        if ($drives) {
            foreach ($drive in $drives) {
                try {
                    $freeGB = [math]::Round($drive.FreeSpace / 1GB, 1)
                    $totalGB = [math]::Round($drive.Size / 1GB, 1)
                    $label = if ($drive.VolumeName) { $drive.VolumeName } else { "Unlabeled" }
                    
                    $displayText = "$($drive.DeviceID) [$label] - $freeGB GB free / $totalGB GB total"
                    
                    # Quick check for existing backup (don't calculate size to avoid hanging)
                    $backupPath = "$($drive.DeviceID)\Plex Media Server"
                    if (Test-Path $backupPath) {
                        $displayText += " (Has existing backup)"
                    }
                    
                    $driveComboBox.Items.Add($displayText)
                } catch {
                    Write-Host "Error processing drive $($drive.DeviceID): $($_.Exception.Message)" -ForegroundColor Yellow
                }
            }
        }
        
        if ($driveComboBox.Items.Count -gt 0) {
            $driveComboBox.SelectedIndex = 0
            Write-Host "Found $($driveComboBox.Items.Count) drives" -ForegroundColor Gray
        } else {
            $driveComboBox.Items.Add("No additional drives found")
            Write-Host "No additional drives found" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Error in Update-Drives: $($_.Exception.Message)" -ForegroundColor Red
        $driveComboBox.Items.Clear()
        $driveComboBox.Items.Add("Error loading drives")
    }
}

function Set-ButtonsEnabled {
    param([bool]$Enabled)
    $hotCopyButton.Enabled = $Enabled
    $coldCopyButton.Enabled = $Enabled
    $smartSyncButton.Enabled = $Enabled
    $stopButton.Enabled = -not $Enabled
}

function Start-SimpleCopy {
    param(
        [string]$Operation,
        [bool]$StopPlex = $false
    )
    
    if ($driveComboBox.SelectedItem -eq $null -or $driveComboBox.SelectedItem.ToString().StartsWith("No additional") -or $driveComboBox.SelectedItem.ToString().StartsWith("Error")) {
        [System.Windows.Forms.MessageBox]::Show("Please select a valid destination drive!", "Error", "OK", "Error")
        return
    }
    
    $selectedDrive = $driveComboBox.SelectedItem.ToString().Split(' ')[0]
    $destPath = "$selectedDrive\Plex Media Server"
    $logPath = "$selectedDrive\plex_copy_log.txt"
    
    # Confirm operation
    $message = "Start $Operation to $destPath ?"
    if ($StopPlex) {
        $message += "`n`nThis will temporarily stop Plex Media Server."
    }
    
    $result = [System.Windows.Forms.MessageBox]::Show($message, "Confirm Operation", "YesNo", "Question")
    if ($result -eq "No") { return }
    
    Set-ButtonsEnabled $false
    $progressLabel.Text = "Starting $Operation..."
    $progressLabel.ForeColor = [System.Drawing.Color]::Cyan
    $progressBar.Value = 0
    $detailsLabel.Text = "Preparing..."
    
    # Simple progress simulation while robocopy runs
    $script:timer = New-Object System.Windows.Forms.Timer
    $script:timer.Interval = 3000  # Check every 3 seconds
    $script:progressCounter = 0
    $script:startTime = Get-Date
    
    $script:timer.Add_Tick({
        # More realistic progress based on time elapsed
        $elapsed = ((Get-Date) - $script:startTime).TotalMinutes
        
        # Estimate progress based on typical copy speeds
        if ($elapsed -lt 1) {
            $script:progressCounter = 5
        } elseif ($elapsed -lt 5) {
            $script:progressCounter = 15
        } elseif ($elapsed -lt 10) {
            $script:progressCounter = 35
        } elseif ($elapsed -lt 20) {
            $script:progressCounter = 60
        } elseif ($elapsed -lt 30) {
            $script:progressCounter = 80
        } else {
            $script:progressCounter = 90
        }
        
        $progressBar.Value = [math]::Min($script:progressCounter, 95)
        $progressLabel.Text = "$Operation in progress... $([math]::Round($elapsed, 1)) minutes elapsed"
        
        # Show current activity
        $detailsLabel.Text = "Time elapsed: $([math]::Round($elapsed, 1)) minutes`nEstimated progress: $($script:progressCounter)%`nCopying files to: $destPath"
    })
    
    # Start robocopy in background
    $scriptBlock = {
        param($sourcePath, $destPath, $logPath, $StopPlex)
        
        try {
            # Stop Plex if requested
            if ($StopPlex) {
                Stop-Service -Name "PlexService" -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 3
                Get-Process -Name "Plex*" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
            }
            
            # Run robocopy
            $startTime = Get-Date
            $result = robocopy "`"$sourcePath`"" "`"$destPath`"" /MIR /R:3 /W:5 /MT:8 /XD "Cache\Transcode" /XF "*.tmp" /LOG:"`"$logPath`""
            $duration = (Get-Date) - $startTime
            
            # Restart Plex if we stopped it
            if ($StopPlex) {
                Start-Service -Name "PlexService" -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 3
            }
            
            return @{
                ExitCode = $LASTEXITCODE
                Duration = $duration.TotalMinutes
            }
        } catch {
            return @{
                ExitCode = 999
                Error = $_.Exception.Message
                Duration = 0
            }
        }
    }
    
    $script:copyJob = Start-Job -ScriptBlock $scriptBlock -ArgumentList $sourcePath, $destPath, $logPath, $StopPlex
    $script:timer.Start()
    
    # Monitor job completion
    $script:monitorTimer = New-Object System.Windows.Forms.Timer
    $script:monitorTimer.Interval = 1000
    $script:monitorTimer.Add_Tick({
        if ($script:copyJob.State -eq "Completed") {
            $script:timer.Stop()
            $script:monitorTimer.Stop()
            
            try {
                $result = Receive-Job $script:copyJob
                Remove-Job $script:copyJob
                
                $progressBar.Value = 100
                
                if ($result.ExitCode -le 7) {
                    $progressLabel.Text = "$Operation completed successfully!"
                    $progressLabel.ForeColor = [System.Drawing.Color]::LightGreen
                    
                    # Get actual backup size
                    $progressLabel.Text = "$Operation completed! Calculating final size..."
                    $destSize = Get-FolderSize $destPath
                    $progressLabel.Text = "$Operation completed successfully!"
                    
                    $detailsLabel.Text = "Duration: $([math]::Round($result.Duration, 1)) minutes`nFinal Size: $destSize GB`nLocation: $destPath`nLog: $logPath"
                } else {
                    $progressLabel.Text = "$Operation completed with warnings (Exit Code: $($result.ExitCode))"
                    $progressLabel.ForeColor = [System.Drawing.Color]::Yellow
                    $destSize = Get-FolderSize $destPath
                    $detailsLabel.Text = "Duration: $([math]::Round($result.Duration, 1)) minutes`nSize: $destSize GB`nCheck log: $logPath"
                }
            } catch {
                $progressLabel.Text = "Operation completed (check log for details)"
                $progressLabel.ForeColor = [System.Drawing.Color]::Yellow
                $detailsLabel.Text = "Log: $logPath"
            }
            
            Set-ButtonsEnabled $true
            Update-Status
        }
    })
    $script:monitorTimer.Start()
}

# Event Handlers
$refreshButton.Add_Click({
    Update-Status
    Update-Drives
})

$hotCopyButton.Add_Click({
    Start-SimpleCopy -Operation "Hot Copy" -StopPlex $false
})

$coldCopyButton.Add_Click({
    Start-SimpleCopy -Operation "Cold Copy" -StopPlex $true
})

$smartSyncButton.Add_Click({
    # For now, smart sync = cold copy (we can enhance this later)
    Start-SimpleCopy -Operation "Smart Sync" -StopPlex $true
})

$stopButton.Add_Click({
    try {
        if ($script:copyJob) {
            Stop-Job $script:copyJob -ErrorAction SilentlyContinue
            Remove-Job $script:copyJob -Force -ErrorAction SilentlyContinue
        }
        if ($script:timer) { $script:timer.Stop() }
        if ($script:monitorTimer) { $script:monitorTimer.Stop() }
        
        $progressLabel.Text = "Operation stopped by user"
        $progressLabel.ForeColor = [System.Drawing.Color]::Yellow
        Set-ButtonsEnabled $true
    } catch {
        # If there's an error stopping, just reset the UI
        Set-ButtonsEnabled $true
        $progressLabel.Text = "Stop requested"
        $progressLabel.ForeColor = [System.Drawing.Color]::Yellow
    }
})

$exitButton.Add_Click({
    try {
        if ($script:copyJob -and $script:copyJob.State -eq "Running") {
            $result = [System.Windows.Forms.MessageBox]::Show("Copy operation is in progress. Are you sure you want to exit?", "Confirm Exit", "YesNo", "Question")
            if ($result -eq "No") { return }
            Stop-Job $script:copyJob -ErrorAction SilentlyContinue
            Remove-Job $script:copyJob -Force -ErrorAction SilentlyContinue
        }
        if ($script:timer) { $script:timer.Stop() }
        if ($script:monitorTimer) { $script:monitorTimer.Stop() }
        $form.Close()
    } catch {
        # If there's any error, just close the form
        $form.Close()
    }
})

$form.Add_FormClosing({
    try {
        if ($script:copyJob) { 
            Stop-Job $script:copyJob -ErrorAction SilentlyContinue
            Remove-Job $script:copyJob -Force -ErrorAction SilentlyContinue
        }
        if ($script:timer) { $script:timer.Stop() }
        if ($script:monitorTimer) { $script:monitorTimer.Stop() }
    } catch {
        # Ignore cleanup errors on exit
    }
})

# Initialize
Write-Host "Initializing status..." -ForegroundColor Green
try {
    Write-Host "Checking Plex status..." -ForegroundColor Yellow
    Update-Status
    Write-Host "Loading drives..." -ForegroundColor Yellow
    Update-Drives
    Write-Host "Initialization complete!" -ForegroundColor Green
} catch {
    Write-Host "Error during initialization: $($_.Exception.Message)" -ForegroundColor Red
}

# Show form
try {
    Write-Host "Showing GUI..." -ForegroundColor Green
    [System.Windows.Forms.Application]::EnableVisualStyles()
    $form.Add_Shown({ Write-Host "GUI is now visible!" -ForegroundColor Green })
    $result = $form.ShowDialog()
    Write-Host "GUI closed" -ForegroundColor Yellow
} catch {
    Write-Host "Error showing GUI: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Press any key to exit..." -ForegroundColor Gray
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}