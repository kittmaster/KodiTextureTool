#Region ;**** Directives created by AutoIt3Wrapper_GUI ****
#AutoIt3Wrapper_Icon=fav.ico
#AutoIt3Wrapper_Outfile=C:\30\KodiXBMCTextureTool-master\source\Kodi.-.Texture.Tool-3.0.1-x32.exe
#AutoIt3Wrapper_Outfile_x64=C:\30\KodiXBMCTextureTool-master\source\Kodi.-.Texture.Tool-3.0.1-x64.exe
#AutoIt3Wrapper_Compile_Both=y
#AutoIt3Wrapper_UseX64=y
#AutoIt3Wrapper_Res_Description=Kodi Texture Tool v3.0.1
#AutoIt3Wrapper_Res_Fileversion=3.0.1.0
#AutoIt3Wrapper_Res_LegalCopyright=by Kittmaster
#AutoIt3Wrapper_Res_Language=1033
#AutoIt3Wrapper_Res_Field=ProductName|Kodi Texture Tool v3.0.1
#EndRegion ;**** Directives created by AutoIt3Wrapper_GUI ****



	#cs ----------------------------------------------------------------------------

	AutoIt Version: 3.3.16.1
	Author: Kittmaster
	Date: 3/17/2024

	Script Function: Compile & Decompile image scripts for Kodi
	Template AutoIt script to .exe creator

	#ce ----------------------------------------------------------------------------

	; Script Start - Add your code below here
	; Create a GUI with various controls.

	;----Global Includes
	#include <GUIConstantsEx.au3>
	#include <String.au3>
	#include <GDIPlus.au3>
	#include <WindowsConstants.au3>
	#include <WinAPI.au3>
	#include <TrayConstants.au3>
	#include <Inet.au3>
	#include <MsgBoxConstants.au3>
	#include <GUIConstantsEx.au3>
	#include <EditConstants.au3>
	#include <Array.au3>
	#include <File.au3>
	;#include <_Dbug.au3>
	
	;----(Housekeeping) Cleans and removes Kodi Texture Tool files from
	;----C:\Temp Folder after program exits
	OnAutoItExitRegister("CleanupFiles")
	Global $aDiagnosticMessages = []

	;----Global variables
	Global $time, $short, $Button
	Global $File, $Download = False, $check = "not checked"
	Global $version = "v3.0.1"
	Global $g_hLog
	Global $AppTitle =  "Kodi Texture Tool"
	Global $buildvalue
	
	;----Remove old log file
	gettime()
	FileDelete(@ScriptDir & "\TextureTool_Log.txt")

	;----Create new log file for current session
	Global $hLog = @ScriptDir & "\TextureTool_Log.txt"
	FileWrite($hLog, ">>> Initialization..." & @CRLF) ; Do not write to edit control, done later.

	;----Start logging startup information for user diagnostics
	FileWrite($hLog, '****************** Program Start *****************' & @CRLF)
	_AddDiagnosticMessage('****************** Program Start *****************') ; Pre GUI diagnostic
	FileWrite($hLog, 'Current Time: ' & $time & @CRLF)
	_AddDiagnosticMessage('Current Time: ' & $time) ; Pre GUI diagnostic
	FileWrite($hLog, 'Running Version: ' & $version & @CRLF)
	_AddDiagnosticMessage('Running Version: ' & $version) ; Pre GUI diagnostic
	$reg = Regread("HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\VisualStudio\10.0\VC\VCRedist\x86","Installed")
	FileWrite($hLog, 'RegRead: HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\VisualStudio\10.0\VC\VCRedist\x86: ' & $reg & @CRLF)
	_AddDiagnosticMessage('RegRead: HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\VisualStudio\10.0\VC\VCRedist\x86: ' & $reg) ; Pre GUI diagnostic

;----64 Bit system files transfers checking
if @OSArch = "x64" then
	;$checkdll = FileExists(@SystemDir & "\msvcp140.dll")
	$checkdll = FileExists(@SystemDir & "\msvcp140.dll") ? "Installed" : "Not Installed"	
	;$checkdll2 = FileExists(@WindowsDir & "\system32\msvcp140.dll")
	$checkdll2 = FileExists(@WindowsDir & "\system32\msvcp140.dll") ? "Installed" : "Not Installed"	
	;$checkdll3 = FileExists(@SystemDir & "\VCRUNTIME140.dll")
	$checkdll3 = FileExists(@SystemDir & "\VCRUNTIME140.dll") ? "Installed" : "Not Installed"	
	;$checkdll4 = FileExists(@WindowsDir & "\system32\VCRUNTIME140.dll")
	$checkdll4 = FileExists(@WindowsDir & "\system32\VCRUNTIME140.dll") ? "Installed" : "Not Installed"	
	FileWrite($hLog, ">>> System DLL integrity check..." & @CRLF)
	_AddDiagnosticMessage(">>> System DLL integrity check...")
	FileWrite($hLog, @SystemDir & "\msvcp140.dll: " & $checkdll & @CRLF)
	_AddDiagnosticMessage(@SystemDir & "\msvcp140.dll: " & $checkdll)
	FileWrite($hLog, @WindowsDir & "\system32\msvcp140.dll: " & $checkdll2 & @CRLF)
	_AddDiagnosticMessage(@WindowsDir & "\system32\msvcp140.dll: " & $checkdll2)
	FileWrite($hLog, @SystemDir & "\VCRUNTIME140.dll: " & $checkdll3 & @CRLF)
	_AddDiagnosticMessage(@SystemDir & "\VCRUNTIME140.dll: " & $checkdll3)
	FileWrite($hLog, @WindowsDir & "\system32\VCRUNTIME140.dll: " & $checkdll4 & @CRLF)
	_AddDiagnosticMessage(@WindowsDir & "\system32\VCRUNTIME140.dll: " & $checkdll4)
	
;if  $checkdll = 0 or $checkdll2 = 0 or $checkdll3 = 0 or $checkdll4 = 0 then
if  $checkdll = "Not Installed" or $checkdll2 = "Not Installed" or $checkdll3 = "Not Installed" or $checkdll4 = "Not Installed" then
	$check = "not installed"
	FileWrite($hLog, ">>> System DLL integrity check...Failed" & @CRLF)
	_AddDiagnosticMessage(">>> System DLL integrity check...Failed")
Endif
Else
	$checkdll2 = FileExists(@WindowsDir & "\system32\msvcp140.dll")
	$checkdll4 = FileExists(@WindowsDir & "\system32\VCRUNTIME140.dll")
;if  $checkdll2 = 0 or $checkdll4 = 0 then
if  $checkdll2 = "Not Installed" or $checkdll4 = "Not Installed" then	
	$check = "not installed"
	FileWrite($hLog, ">>> System DLL integrity check...Failed" & @CRLF)
	_AddDiagnosticMessage(">>> System DLL integrity check...Failed")
Endif
	FileWrite($hLog, @WindowsDir & "\system32\msvcp140.dll: " & $checkdll2 & @CRLF)
	_AddDiagnosticMessage(@WindowsDir & "\system32\msvcp140.dll: " & $checkdll2)
	FileWrite($hLog, @WindowsDir & "\system32\VCRUNTIME140.dll: " & $checkdll4 & @CRLF)
	_AddDiagnosticMessage(@WindowsDir & "\system32\VCRUNTIME140.dll: " & $checkdll4)
Endif
	FileWrite($hLog, ">>> System DLL integrity check...Passed" & @CRLF)
	_AddDiagnosticMessage(">>> System DLL integrity check...Passed")

	;----Enable Dev Mode
	FileWrite($hLog, ">>> Set DEV hot key sequence..." & @CRLF)
	_AddDiagnosticMessage(">>> Set DEV hot key sequence...")
	HotKeySet("+!d", "enable_dev")
	FileWrite($hLog, ">>> Set DEV hot key sequence... Complete" & @CRLF)
	_AddDiagnosticMessage(">>> Set DEV hot key sequence... Complete")
	FileWrite($hLog, ">>> To enable DEV Mode press and hold the keyboard sequence: ""Shift"" > ""Alt"" > ""D"" " & @CRLF)
	_AddDiagnosticMessage(">>> To enable DEV Mode press and hold the keyboard sequence: ""Shift"" > ""Alt"" > ""D""")

;----Visual Studio Redistributable Notification
If Not FileExists("C:\temp" & "\Kodi.dat") Then
	FileWrite($hLog, ">>> Notification of latest TexturePacker in use and how to fix if issue arises..." & @CRLF)
	_AddDiagnosticMessage(">>> Notification of latest TexturePacker in use and how to fix if issue arises...")
	FileWrite("C:\temp" & "\Kodi.dat", "Kodi texture tool message handler")
	_AddDiagnosticMessage("Kodi texture tool message handler")
	$lol = MsgBox($MB_YESNO, "Kodi - Texture Tool", _
		"TextureTool is using the latest TexturePacker, if it's not working in your case, " & _
		"please install the latest Visual C++ Redistributable for Visual Studio." & _
		@CRLF & "Click ""Yes"" to launch a browser and download the required C++ redistributables or click ""No"" to close " & _
		"this dialog and use the program.")

	If $lol = 6 Then
		ShellExecute("https://www.microsoft.com/de-DE/download/details.aspx?id=48145")
	EndIf
	gettime()
	FileWrite($hLog, $short & ": " & 'User notified vcredist once complete, notification will not re-appear' & @CRLF)
	_AddDiagnosticMessage($short & ": " & 'User notified vcredist once complete, notification will not re-appear')
	FileWrite($hLog, ">>> Notification of latest TexturePacker in use and how to fix if issue arises... Complete" & @CRLF)
	_AddDiagnosticMessage(">>> Notification of latest TexturePacker in use and how to fix if issue arises... Complete")
EndIf

	;----Set tray options mode
	Opt("TrayMenuMode", 3)

	;----Force create local folder for files to run in
	FileWrite($hLog, ">>> Create temporary local folder ""C:\temp""..." & @CRLF)
	_AddDiagnosticMessage(">>> Create temporary local folder ""C:\temp""...")
	DirCreate ( "C:\temp" )
	FileWrite($hLog, ">>> Create temporary local folder ""C:\temp""... Complete" & @CRLF)
	_AddDiagnosticMessage(">>> Create temporary local folder ""C:\temp""... Complete")

	;----Copy files to local non-privileged folder for operation
	FileWrite($hLog, ">>> Copy requisite operational files to non-privileged temporary local folder ""C:\temp""..." & @CRLF)
	_AddDiagnosticMessage(">>> Copy requisite operational files to non-privileged temporary local folder ""C:\temp""...")
	FileInstall("C:\30\KodiXBMCTextureTool-master\source\vcruntime140.dll", "C:\temp" & "\vcruntime140.dll", 1)
	FileInstall("C:\30\KodiXBMCTextureTool-master\source\msvcp140.dll", "C:\temp" & "\msvcp140.dll", 1)
	FileInstall("C:\30\KodiXBMCTextureTool-master\source\base.exe", "C:\temp" & "\base.exe", 1)
	FileInstall("C:\30\KodiXBMCTextureTool-master\source\D3DX9_43.dll", "C:\temp" & "\D3DX9_43.dll", 1)
	FileInstall("C:\30\KodiXBMCTextureTool-master\source\TexturePacker.exe", "C:\temp" & "\TexturePacker.exe", 1)
	FileInstall("C:\30\KodiXBMCTextureTool-master\source\kodi.png", "C:\temp" & "\kodi.png", 1)
	FileWrite($hLog, ">>> Copy requisite operational files to non-privileged temporary local folder ""C:\temp""... Complete" & @CRLF)
	_AddDiagnosticMessage(">>> Copy requisite operational files to non-privileged temporary local folder ""C:\temp""... Complete")

	;----TexturePacker Information
	FileWrite($hLog, ">>> Get TexturePacker version..." & @CRLF)
	_AddDiagnosticMessage(">>> Get TexturePacker version...")
	Local $txtv = FileGetVersion("C:\temp" & "\TexturePacker.exe")
	gettime()
	FileWrite($hLog, $short & ": " & 'TexturePacker version: ' & "v" & $txtv & @CRLF)
	_AddDiagnosticMessage($short & ": " & 'TexturePacker version: ' & "v" &  $txtv)

	Local $modifiedTime = FileGetTime("C:\temp" & "\TexturePacker.exe", $FT_MODIFIED, 0)
If  $modifiedTime = 0 Then
    MsgBox($MB_SYSTEMMODAL, "", "Failed to get file time")
Else
    Local $formattedDate = FormatDate($modifiedTime)
EndIf
	gettime()
	FileWrite($hLog, $short & ": " & 'TexturePacker modified date: ' & $formattedDate & @CRLF)
	_AddDiagnosticMessage($short & ": " & 'TexturePacker modified date: ' & $formattedDate)

	gettime()
	FileWrite($hLog, $short & ": " & 'TexturePacker status: Stable' & @CRLF)
	_AddDiagnosticMessage($short & ": " & 'TexturePacker status: Stable')

	Local $iFileSize = FileGetSize("C:\temp" & "\TexturePacker.exe")
	gettime()
	FileWrite($hLog, $short & ": " & 'TexturePacker file size: ' & ByteSuffix($iFileSize) & @CRLF)
	_AddDiagnosticMessage($short & ": " & 'TexturePacker file size: ' & ByteSuffix($iFileSize))

	FileWrite($hLog, ">>> Get TexturePacker version... Complete" & @CRLF)
	_AddDiagnosticMessage(">>> Get TexturePacker version... Complete")

	;----Check Repository
	FileWrite($hLog, ">>> Checking repository for an update..." & @CRLF)
	_AddDiagnosticMessage(">>> Checking repository for an update...")
	$Update_Check = 0
	update() ; Check repository for updates (WIP) - Not operational yet
	FileWrite($hLog, ">>> Checking repository for an update... Complete" & @CRLF)
	_AddDiagnosticMessage(">>> Checking repository for an update... Complete")

	;----Create GUI and all of its elements
Func gui()

;----On first run, show user control creating routine, during update, disable message
If  $Update_Check = 0 Then
	FileWrite($hLog, ">>> Create GUI and all user elements..." & @CRLF)
EndIf

	;Global $g_hGUI = GUICreate("Kodi Texture Tool" & $version, 800, 520) ; Increase the width to accommodate the log control	
	Global $g_hGUI = GUICreate($AppTitle & " " & $version, 800, 520) ; Increase the width to accommodate the log control


	; Load the image
	_GDIPlus_Startup()
	Global $g_hImage = _GDIPlus_ImageLoadFromFile("C:\temp\kodi.png")
	Global $g_hGraphic = _GDIPlus_GraphicsCreateFromHWND($g_hGUI)
	_GDIPlus_GraphicsDrawImage($g_hGraphic, $g_hImage, 0, 0) ; Draw the image at position (0,0)

	; Create the log control	 	
	Global $g_hLog = GUICtrlCreateEdit("", 300, 0, 500, 520, $ES_READONLY + $WS_VSCROLL + $ES_MULTILINE, 0)

	; Set the initial data
	GUICtrlSetData($g_hLog, ">>> Initialization..." & @CRLF, 1)
	
	; Push the diagnostic messages to the edit control
	For $i = 0 To UBound($aDiagnosticMessages) - 1
		GUICtrlSetData($g_hLog, $aDiagnosticMessages[$i] & @CRLF, 1)
	Next
	
	$hLabel = GUICtrlCreateLabel("Decompile Mode:", 84, 180, 130, 16)
	GUICtrlSetFont($hLabel, 10, 1000) ; Set the font weight to 1000 for stronger bold
	GUICtrlSetState(-1, $GUI_ENABLE)
	$hLabel = GUICtrlCreateLabel("Compile Mode:", 86, 316, 130, 16)
	GUICtrlSetFont($hLabel, 10, 1000) ; Set the font weight to 1000 for stronger bold
	GUICtrlSetState(-1, $GUI_ENABLE)
	$select = GUICtrlCreateButton("Select input file", 180, 210, 100, 25) ; Decompile Section
	GUICtrlSetTip($select, "Select .xbt to decompile")
	$output = GUICtrlCreateButton("Select output", 180, 240, 100, 25) ; Decompile Section
	GUICtrlSetTip($output, "Select folder to extract texture images to")
	GUICtrlSetState(-1, $GUI_DISABLE) ; Decompile Section
	$start = GUICtrlCreateButton("Start", 180, 270, 100, 25) ; Decompile Section
	GUICtrlSetTip($start, "Start decompile extraction")
	GUICtrlSetState(-1, $GUI_DISABLE) ; Decompile Section
	
	; Display the GUI
	GUICtrlCreateLabel("1. Select the input file:", 10, 215, 150, 25) ; Decompile Section
	GUICtrlCreateLabel("2. Select the output directory:", 10, 245, 150, 25) ; Decompile Section
	GUICtrlCreateLabel("3. Press start to begin:", 10, 275, 150, 25) ; Decompile Section
	$info = GUICtrlCreateButton("?", 260, 5, 20, 20) ; About dialog
	GUICtrlSetTip($info, "Updates/Support/Info/Wiki")
	$clearlog = GUICtrlCreateButton("X", 260, 25, 20, 20) ; About dialog
	GUICtrlSetTip($clearlog, "Clear event log")
	$status = GUICtrlCreateLabel("Welcome! Select mode >> Compile / Decompile mode", 11, 485, 290, 20)
	GUICtrlSetFont(-1, 8.5)
	GUICtrlSetState(-1, $GUI_ENABLE)
	$lz0 = GUICtrlCreateCheckbox("Enable lz0", 20, 435, 100, 25) ; Deprecated, reasons unknown
	GUICtrlSetState($lz0, $GUI_HIDE)
	;GUICtrlSetState(-1, $GUI_UNCHECKED)
	;GUICtrlSetState(-1, $GUI_DISABLE)
	$dupecheck = GUICtrlCreateCheckbox("Enable dupecheck", 130, 435, 130, 25)
	$sublog = GUICtrlCreateRadio("Submit log - Click me", 130, 455, 130, 25)
	global $dev = GUICtrlCreateCheckbox("Dev mode", 20, 455, 90, 25)
	GUICtrlSetState(-1, $GUI_DISABLE)
	global $progress = GUICtrlCreateProgress(9, 505, 275, 10)
	;GUICtrlSetState($lz0, $GUI_UNCHECKED) ; Set the checkbox as unchecked initially ; Deprecated, Reasons Unknown
	GUICtrlSetState($dev, $GUI_UNCHECKED) ; Set the checkbox as unchecked initially
	;#-------------------------------------------------------------------------
	$select2 = GUICtrlCreateButton("Select input folder", 180, 340, 100, 25) ; Compile Section
	GUICtrlSetTip($select2, "Select folder with source images")
	$output2 = GUICtrlCreateButton("Select output file", 180, 370, 100, 25) ; Compile Section
	GUICtrlSetTip($output2, "Select folder to compile texture file")
	GUICtrlSetState(-1, $GUI_DISABLE) ; Compile Section
	$start2 = GUICtrlCreateButton("Start", 180, 400, 100, 25) ; Compile Section
	GUICtrlSetTip($start2, "Start compile process")
	GUICtrlSetState(-1, $GUI_DISABLE) ; Compile Section
	GUICtrlCreateLabel("1. Select the input directory:", 10, 345, 150, 25) ; Compile Section
	GUICtrlCreateLabel("2. Select the output file:", 10, 375, 150, 25) ; Compile Section
	GUICtrlCreateLabel("3. Press start to begin:", 10, 405, 150, 25) ; Compile Section
	GUIRegisterMsg($WM_PAINT, "MY_WM_PAINT")
	GUISetState(@SW_SHOW)
	GUICtrlSetState($lz0, $GUI_HIDE)
		
	;----GUI Visual Buttons as Borders
	GUICtrlCreateButton("", 0, 305, 295, 5);  Center Border Compile / Decompile
	GUICtrlSetState(-1, $GUI_DISABLE)
	GUICtrlCreateButton("", 293, -5, 5, 530);  Right Border
	GUICtrlSetState(-1, $GUI_DISABLE)


	$thread = TrayCreateItem("Visit Thread", -1, -1, $TRAY_ITEM_NORMAL)
	$git = TrayCreateItem("Check Github", -1, -1, $TRAY_ITEM_NORMAL)
	$update = TrayCreateItem("Check for updates", -1, -1, $TRAY_ITEM_NORMAL)
	$dona = TrayCreateItem("Donate BTC - Disabled", -1, -1, $TRAY_ITEM_NORMAL)

	TrayCreateItem("") ; Create a separator line.
	Local $idAbout = TrayCreateItem("About")
	TrayCreateItem("") ; Create a separator line.
	Local $idExit = TrayCreateItem("Exit")
	TraySetState($TRAY_ICONSTATE_SHOW) ; Show the tray menu.		

If $Update_Check = 0 Then
	FileWrite($hLog, ">>> Create GUI and all user elements... Complete" & @CRLF)
	GUICtrlSetData($g_hLog, ">>> Create GUI and all user elements... Complete" & @CRLF, 1)
EndIf
	FileWrite($hLog, ">>> Initialization... Complete" & @CRLF)
	GUICtrlSetData($g_hLog, ">>> Initialization... Complete" & @CRLF, 1)
	FileWrite($hLog, ">>> Ready" & @CRLF)
	GUICtrlSetData($g_hLog, ">>> Ready" & @CRLF, 1)


; Loop until the user exits.
While 1
	Switch GUIGetMsg()
		Case $GUI_EVENT_CLOSE
			;----Program closed by user log message
			FileWrite($hLog, '****************** Closed by User *****************' & @CRLF)
			GUICtrlSetData($g_hLog, "****************** Closed by User *****************" & @CRLF, 1)
			Exit
			ExitLoop
			ProcessClose(@ScriptName)		
			
		Case $select
			;----Start of decompile mode
			FileWrite($hLog, '****************** Decompile Mode Selected *****************' & @CRLF)
			GUICtrlSetData($g_hLog, "****************** Decompile Mode Selected *****************" & @CRLF, 1)
			gettime()
			FileWrite($hLog, $short & ": " & 'Decompile mode initiated' & @CRLF)
			GUICtrlSetData($g_hLog, $short & ": " & 'Decompile mode initiated' & @CRLF, 1)
			$folder_path = IniRead(@ScriptDir & "\config.ini", "Paths", "DecompileInputFileSaveLocation", "%SystemDrive%\")
			$selected = FileOpenDialog("Select .xbt file to extract...", $folder_path, "Kodi Texture File (*.xbt)")
			If $selected <> "" Then				
				; Get the filename
				$filename = "Textures.xbt"
				; Get the length of the filename
				$filename_length = StringLen($filename)
				; Trim the filename from the selected path to get the folder path
				$folder_path = StringTrimRight($selected, $filename_length)				
				; Save the selected path to config.ini
				$writeResult = IniWrite(@ScriptDir & "\config.ini", "Paths", "DecompileInputFileSaveLocation", $folder_path)
				If $writeResult == 0 Then
					MsgBox(0, "Error", "Failed to write to INI file.")
				EndIf
				
				GUICtrlSetData($status, "Step 2 enabled >> Select save location folder")
				gettime()
				FileWrite($hLog, $short & ": " & 'Decompile input file: ' & '"' & $selected & '"' & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & 'Decompile input file: ' & '"' & $selected & '"' & @CRLF, 1)
				FileWrite($hLog, ">>> Input selection loaded successfully" & @CRLF)
				GUICtrlSetData($g_hLog, ">>> Input selection loaded successfully" & @CRLF, 1)
				GUICtrlSetState($output, $GUI_ENABLE)
			EndIf
	
			;GUISetState()
			
		Case $sublog
			;----Radio button - Launches Messagebox, launches Browser to report issue on Kodi's forum
			FileWrite($hLog, ">>> Submit log radio button selected" & @CRLF)
			GUICtrlSetData($g_hLog, ">>> Submit log radio button selected" & @CRLF, 1)	
			MsgBox(0, "Submit Log", "I can only support Kodi - Texture Tool." & @CRLF & _
									"The software used here (TexturePacker/TextureExtraction) is not developed by me." & @CRLF & _
									"Everytime you use the Kodi - Texture Tool a logfile is created, which gets automatically" & _
									"deleted when you restart the tool." & @CRLF & "Find your log here: " & _
									@ScriptDir & "\TextureTool_log.txt" & @CRLF & "Submit your issue including the logfile AFTER you" & _
									"started to compile/decompile and i'll try to help you out.")
			ShellExecute("http://forum.kodi.tv/newreply.php?tid=201883")
			ShellExecute(@ScriptDir & "\TextureTool_log.txt")
			
		Case $output
			;----Decompile mode
			gettime()
			;$outputed = FileSelectFolder("Select save location folder...", "C:\")
			$outputed = FileSelectFolder("Select save location folder...", IniRead(@ScriptDir & "\config.ini", "Paths", _ 
									     "DecompileOutputFolderSaveLocation", "%SystemDrive%\"))
			FileWrite($hLog, $short & ": " & 'Path to output directory: ' & '"' & $outputed & '"' & @CRLF)					
			If $outputed <> "" Then
				; Save the selected path to config.ini
				$writeResult = IniWrite(@ScriptDir & "\config.ini", "Paths", "DecompileOutputFolderSaveLocation", $outputed)
				If $writeResult == 0 Then
					MsgBox(0, "Error", "Failed to write to INI file.")
				EndIf
				GUICtrlSetData($status, "Step 3 enabled >> Press the start button to execute")
				gettime()
				FileWrite($hLog, $short & ": " & 'Decompile output directory: ' & '"' & $outputed & '"' & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & 'Decompile output directory: ' & '"' & $outputed & '"' & @CRLF, 1)
				FileWrite($hLog, ">>> Output folder destination loaded successfully" & @CRLF)
				GUICtrlSetData($g_hLog, ">>> Output folder destination loaded successfully" & @CRLF, 1)
				GUICtrlSetState($start, $GUI_ENABLE)
			EndIf
			;GUISetState()
			
		Case $start
			;----Decompile mode start decompile execution
			;msgbox(0,"",$command) ; Use for diagnostics
			FileWrite($hLog, ">>> Decompilation start button pressed - Decompilation begins" & @CRLF)
			GUICtrlSetData($g_hLog, ">>> Decompilation start button pressed - Decompilation begins" & @CRLF, 1)
			ProcessClose("base.exe")
			$command = "base.exe " & '"' & $selected & '"' & ' "' & $outputed & '"'
			gettime()
			FileWrite($hLog, $short & ": " & 'Running command:' & $command & @CRLF) ; Closing double quote not needed, derived from $outputed
			GUICtrlSetData($g_hLog, $short & ": " & 'Running command:' & $command & @CRLF, 1)
			$pid = run(@ComSpec & " /c " & $command, "C:\temp", @SW_HIDE)
			GUICtrlSetData($status, "Decompile in progress... Please wait")
			TrayTip("Kodi - Texture Tool", "Decompile in progress - Please wait...", 2, 1)
			AdlibRegister("progressbar2", 1400) ; Call progressbar2() every 100 milliseconds
			gettime()
			FileWrite($hLog, $short & ": " & 'Decompiling...base.exe is running' & @CRLF)
			GUICtrlSetData($g_hLog, $short & ": " & 'Decompiling...base.exe is running' & @CRLF, 1)
			processwaitclose($pid)
			AdlibUnRegister("progressbar2") ; Unregister the function when the process is done
			gettime()
			FileWrite($hLog, $short & ": " & 'Decompiling complete...base.exe closed' & @CRLF)
			GUICtrlSetData($g_hLog, $short & ": " & 'Decompiling complete...base.exe closed' & @CRLF, 1)
			GUICtrlSetData($progress, 100)
			GUICtrlSetData($status, "Decompilation of the texture file complete")
			ShellExecute($outputed)
			gettime()
			FileWrite($hLog, $short & ": " & 'Opened destination directory' & @CRLF)
			GUICtrlSetData($g_hLog, $short & ": " & 'Opened destination directory' & @CRLF, 1)
			FileWrite($hLog, '****************** Decompile Complete *****************' & @CRLF)
			GUICtrlSetData($g_hLog, "****************** Decompile Complete *****************" & @CRLF, 1)
			GUICtrlSetState($output, $GUI_DISABLE) ; Decompile complete, reset lockout controls
			GUICtrlSetState($start, $GUI_DISABLE) ; Decompile complete, reset lockout controls
			;GUICtrlSetData($progress, 0)
			FileWrite($hLog, '>>> Decompile user controls reset for next operation' & @CRLF)
			GUICtrlSetData($g_hLog, ">>> Decompile user controls reset for next operation" & @CRLF, 1)
			;----Decompile mode complete			
			
			Case $select2
			;----Start of Compile mode
			FileWrite($hLog, '****************** Compile Mode Selected *****************' & @CRLF)
			GUICtrlSetData($g_hLog, "****************** Compile Mode Selected *****************" & @CRLF, 1)
			;----Check if Visual C++ Redistributables are installed
			if $check = "not installed" Then
				$abox = msgbox(4,"Critical Error","Visual C++ Redistributable for Visual Studio seems not to be installed, TexturePacker will not work!" & @crlf & _
												  "Texture Tool will patch your system with Visual C++ package dll's." & @crlf & @crlf & _
												  "Do you want to patch those files now?")
				if $abox = 6 then
					Filecopy("C:\temp" & "\msvcp140.dll",@WindowsDir & "\system32\" & "msvcp140.dll")
					Filecopy("C:\temp" & "\vcruntime140.dll",@WindowsDir & "\system32\" & "vcruntime140.dll")
					Filecopy("C:\temp" & "\msvcp140.dll",@SystemDir & "\msvcp140.dll")
					Filecopy("C:\temp" & "\vcruntime140.dll",@SystemDir & "\vcruntime140.dll")
					FileWrite($hLog, $short & ": " & 'Systemfiles patched for VCREDIST!' & @CRLF)
					GUICtrlSetData($g_hLog, $short & ": " & 'Systemfiles patched for VCREDIST!' & @CRLF, 1)
				EndIf
			Endif
			;----Start of Compile mode image folder Selection
			gettime()
			FileWrite($hLog, $short & ": " & 'Compile mode initiated' & @CRLF)
			GUICtrlSetData($g_hLog, $short & ": " & 'Compile mode initiated' & @CRLF, 1)
			;$outputedd = FileSelectFolder("Select images source folder for .xbt file...", "C:\")
			$outputedd = FileSelectFolder("Select images source folder for .xbt file...", IniRead(@ScriptDir & "\config.ini", "Paths", _ 
										  "CompileInputFolderSaveLocation", "%SystemDrive%\"))
			If StringInStr($outputedd, " ") Then
				gettime()
				FileWrite($hLog, $short & ": " & 'One or more whitespace(s) found in compile SOURCE path! User notified' & @CRLF)
				;GUICtrlSetData($g_hLog, ">>> One or more whitespace(s) found in compile SOURCE path! User notified" & @CRLF, 1)
				GUICtrlSetData($g_hLog, $short & ": " & 'One or more whitespace(s) found in compile SOURCE path! User notified' & @CRLF, 1)
				MsgBox(0, "Kodi - Texture Tool - Decompile White Space Error", "Kodi Texture Tool has found one or more whitespaces(s) in the DECOMPILE INPUT " & _ 
												 "DIRECTORY folder path!" & @CRLF & @CRLF & _
												 "Path selected: " & '"' & $outputedd & '"' & @CRLF & @CRLF & _
											     "Verify your DECOMPILE INPUT DIRECTORY folder path doesn't have a folder name that looks like this " & _  
												 "example: 'New Folder'. " & @CRLF & @CRLF & _
											     "Suggested Fix: Rename any folder within the folder path using an underscore to resolve the issue. " & _ 
												 "Your folder should look like this: 'New_Folder'" & @CRLF & @CRLF & _ 
												 "Adjust & try again!")
			Else 
				
				If $outputedd <> "" Then
					; Save the selected path to config.ini
					$writeResult = IniWrite(@ScriptDir & "\config.ini", "Paths", "CompileInputFolderSaveLocation", $outputedd)
					If $writeResult == 0 Then
						MsgBox(0, "Error", "Failed to write to INI file.")
					EndIf
					GUICtrlSetData($status, "Step 2 enabled >> Select save location folder")
					gettime()
					FileWrite($hLog, ">>> Image folder input selection loaded successfully" & @CRLF)
					GUICtrlSetData($g_hLog, ">>> Image folder input selection loaded successfully" & @CRLF, 1)
					FileWrite($hLog, $short & ": " & 'Path to directory: ' & '"' & $outputedd & '"' & @CRLF)
					GUICtrlSetData($g_hLog, $short & ": " & 'Path to directory: ' & '"' & $outputedd & '"' & @CRLF, 1)
					GUICtrlSetState($output2, $GUI_ENABLE)
				EndIf
			EndIf
			
		Case $output2
			;----Start of Compile mode Textures.xbt destination folder selection
			;$selected2 = FileSaveDialog("Select save location folder for .xbt file...", "C:\", "Kodi Texture File (*.xbt)", 0, "Textures.xbt")
			$selected2 = FileSaveDialog("Select save location folder for .xbt file...", IniRead(@ScriptDir & "\config.ini", "Paths", _ 
										"CompileOutputFileSaveLocation", "%SystemDrive%\"), "Kodi Texture File (*.xbt)", 0, "Textures.xbt")
			If StringInStr($selected2, " ") Then
				gettime()
				FileWrite($hLog, $short & ": " & 'One or more whitespace(s) found in compile DESTINATION path! User notified' & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & 'One or more whitespace(s) found in compile DESTINATION path! User notified' & @CRLF, 1)
				MsgBox(0, "Kodi - Texture Tool - Compile White Space Error", "Kodi Texture Tool has found one or more whitespaces(s) in the COMPILE OUTPUT " & _ 
												 "folder path!" & @CRLF & @CRLF & _
												 "Path selected: " & '"' & $selected2 & '"' & @CRLF & @CRLF & _
											     "Verify your COMPILE OUTPUT folder path doesn't have a folder name that looks like this " & _  
												 "example: 'New Folder'. " & @CRLF & @CRLF & _
											     "Suggested Fix: Rename any folder within the folder path using an underscore to resolve the issue. " & _ 
												 "Your folder should look like this: 'New_Folder'" & @CRLF & @CRLF & _ 
												 "Adjust & try again!")
			Else
				gettime()
				
				; Get the filename
				$filename = "Textures.xbt"

				; Get the length of the filename
				$filename_length = StringLen($filename)

				; Trim the filename from the selected path to get the folder path
				$folder_path = StringTrimRight($selected2, $filename_length)
				
				If $selected2 <> "" Then
					; Save the selected path to config.ini
					$writeResult = IniWrite(@ScriptDir & "\config.ini", "Paths", "CompileOutputFileSaveLocation", $folder_path)
					If $writeResult == 0 Then
						MsgBox(0, "Error", "Failed to write to INI file.")
					EndIf
					GUICtrlSetData($status, "Step 3 enabled >> Press the start button to execute")
					gettime()
					FileWrite($hLog, $short & ": " & 'Path to output file: ' & '"' & $selected2 & '"' & @CRLF)
					GUICtrlSetData($g_hLog, $short & ": " & 'Path to output file: ' & '"' & $selected2 & '"' & @CRLF, 1)					
					FileWrite($hLog, $short & ": " & 'Output folder destination loaded successfully' & @CRLF)
					GUICtrlSetData($g_hLog, $short & ": " & 'Output folder destination loaded successfully' & @CRLF, 1)
					GUICtrlSetState($start2, $GUI_ENABLE)
				EndIf
			EndIf

		Case $start2
			;----Compile mode start decompile execution
			FileWrite($hLog, ">>> Compilation start button pressed - Compilation begins" & @CRLF)
			GUICtrlSetData($g_hLog, ">>> Compilation start button pressed - Compilation begins" & @CRLF, 1)
			ProcessClose("TexturePacker.exe")
			gettime()
			;----Parse user options to pass to compiler engine
			If GUICtrlRead($dupecheck) = $GUI_CHECKED Then
				$command = "TexturePacker -disable_lz0 -dupecheck -input " & $outputedd & " -output " & $selected2
				FileWrite($hLog, $short & ": " & 'Running command: ' & $command & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & 'Running command: ' & $command & @CRLF, 1)

			ElseIf GUICtrlRead($dupecheck) = $GUI_UNCHECKED Then
				$command = "TexturePacker -disable_lz0 -input " & $outputedd & " -output " & $selected2
				FileWrite($hLog, $short & ": " & 'Running command:' & $command & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & 'Running command:' & $command & @CRLF, 1)

			ElseIf GUICtrlRead($dev) = $GUI_CHECKED Then
				MsgBox(0, "Dev Mode", "Running command: " & $command)
				FileWrite($hLog, $short & ": " & 'Dev Mode enabled - displayed command to user' & $command & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & 'Dev Mode enabled - displayed command to user' & $command & @CRLF, 1)
			EndIf
			$pid = Run(@ComSpec & " /c " & $command, "C:\temp", @SW_HIDE)
			GUICtrlSetData($status, "Compile in progress... Please wait")
			TrayTip("Kodi - Texture Tool", "Compile in progress - Please wait...", 2, 1)
			AdlibRegister("progressbar1", 2400) ; Call progressbar1() every 2400 milliseconds
			gettime()
			FileWrite($hLog, $short & ": " & 'Compiling...TexturePacker.exe is running' & @CRLF)
			GUICtrlSetData($g_hLog, $short & ": " & 'Compiling...TexturePacker.exe is running' & @CRLF, 1)
			processwaitclose($pid)
			AdlibUnRegister("progressbar1") ; Unregister the function when the process is done
			gettime()
			FileWrite($hLog, $short & ": " & 'Compile complete...TexturePacker.exe closed' & @CRLF)
			GUICtrlSetData($g_hLog, $short & ": " & 'Compile complete...TexturePacker.exe closed' & @CRLF, 1)
			GUICtrlSetData($progress, 100)
			GUICtrlSetData($status, "Compilation of the texture file complete")
			ShellExecute($folder_path)
			gettime()
			FileWrite($hLog, $short & ": " & 'Opened destination directory' & @CRLF)
			GUICtrlSetData($g_hLog, $short & ": " & 'Opened destination directory' & @CRLF, 1)
			FileWrite($hLog, '****************** Compile Complete *****************' & @CRLF)
			GUICtrlSetData($g_hLog, "****************** Compile Complete *****************" & @CRLF, 1)
			GUICtrlSetState($output2, $GUI_DISABLE) ; Compile complete, reset lockout controls
			GUICtrlSetState($start2, $GUI_DISABLE) ; Compile complete, reset lockout controls
			;GUICtrlSetData($progress, 0)
			FileWrite($hLog, '>>> Compile user controls reset for next operation' & @CRLF)
			GUICtrlSetData($g_hLog, ">>> Compile user controls reset for next operation" & @CRLF, 1)			
			;----Compile mode complete			
					
		Case $info
			child()
			
		Case $clearlog
			ClearEdit()
			
	EndSwitch
	Switch TrayGetMsg()
		Case $idAbout ;
			child()
			
		Case $idExit ; Exit the loop.
			FileWrite($hLog, '****************** Closed About Window by User *****************' & @CRLF)
			GUICtrlSetData($g_hLog, "****************** Closed About Window by User *****************" & @CRLF, 1)
			ProcessClose(@ScriptName)
			ExitLoop
			Exit
			
		Case $update
			update()
			
		Case $thread
			ShellExecute("http://forum.kodi.tv/showthread.php?tid=201883")
			
		Case $git
			ShellExecute("https://github.com/e0xify/KodiXBMCTextureTool")
			
		case $dona
			Msgbox(0,"BTC Donation - Disabled","Donation address copied to clipboard" & @crlf & "Many thanks :)")
				ClipPut("")
				
	EndSwitch
WEnd
Endfunc

;----About window button text info
Func child()
	gettime()
	FileWrite($hLog, $short & ": " & 'About window opened' & @CRLF)
	GUICtrlSetData($g_hLog, $short & ": " & 'About window opened' & @CRLF, 1)

	; Create a GUI with various controls.
	Local $hGUI = GUICreate("About", 200, 210)
	Local $idOK = GUICtrlCreateButton("OK", 310, 370, 85, 25)
	$lbl2 = GUICtrlCreateButton("Release Thread", 15, 20, 170, 25)
	$lbl3 = GUICtrlCreateButton("GitHub Repo", 15, 50, 170, 25)
	$lbl5 = GUICtrlCreateButton("Kodi Wiki", 15, 80, 170, 25)
	$lbl6 = GuictrlCreateButton("Donate BTC - Disabled",15,110,170,25)
	$lbl4 = GUICtrlCreateButton("Check for updates", 15, 140, 170, 25)

	GUICtrlCreateLabel("Created by Kittmaster - " & $version, 30, 180, 220, 25)
	GUICtrlSetState(-1, $GUI_DISABLE)
	; Display the GUI.
	GUISetState(@SW_SHOW, $hGUI)

	; Loop until the user exits.
	While 1
		Switch GUIGetMsg()
			Case $GUI_EVENT_CLOSE, $idOK
				gettime()
				FileWrite($hLog, $short & ": " & 'About window closed' & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & 'About window closed' & @CRLF, 1)
				ExitLoop
			Case $lbl2
				gettime()
				ShellExecute("http://forum.kodi.tv/showthread.php?tid=201883")
				FileWrite($hLog, $short & ": " & "Release Thread button selected >> Kodi URL opened in default browser" & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & "Release Thread button selected >> Kodi URL opened in default browser" & @CRLF, 1)
			Case $lbl3
				gettime()
				ShellExecute("https://github.com/e0xify/KodiXBMCTextureTool")
				FileWrite($hLog, $short & ": " & "GitHub Repo button selected >> GitHub Repo URL opened in default browser" & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & "GitHub Repo button selected >> GitHub Repo URL opened in default browser" & @CRLF, 1)
			Case $lbl4
				$Update_Check = 1
				update()
				gettime()
				FileWrite($hLog, $short & ": " & 'Check for updates button selected - (WIP)Function temporarily disabled' & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & 'Check for updates button selected - (WIP)Function temporarily disabled' & @CRLF, 1)
			case $lbl5
				ShellExecute("http://kodi.wiki/view/TextureTool")
				gettime()
				FileWrite($hLog, $short & ": " & 'Kodi Wiki button selected >> Kodi Wiki URL opened in default browser' & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & 'Kodi Wiki button selected >> Kodi Wiki URL opened in default browser' & @CRLF, 1)
			case $lbl6
				gettime()
				FileWrite($hLog, $short & ": " & 'Donate BTC - Disabled button selected - Disabled' & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & 'Donate BTC - Disabled button selected - Disabled' & @CRLF, 1)
				Msgbox(0,"BTC Donation - DISABLED","Donation address copied to clipboard - DISABLED" & @CRLF & "Many thanks :)")
				ClipPut("") ; Disabled Author AWOL
		EndSwitch
	WEnd

	; Delete the previous GUI and all controls.
	GUIDelete($hGUI)
EndFunc   ;==>child

	; Clean up GDI+ resources
	_GDIPlus_GraphicsDispose($g_hGraphic)
	_GDIPlus_ImageDispose($g_hImage)
	_GDIPlus_Shutdown()

;----Draw PNG image
Func MY_WM_PAINT($hWnd, $iMsg, $wParam, $lParam)
	#forceref $hWnd, $iMsg, $wParam, $lParam
	_GDIPlus_ImageResize($g_hImage, 20, 20)
	_WinAPI_RedrawWindow($g_hGUI, 0, 0, $RDW_UPDATENOW)

	_GDIPlus_GraphicsDrawImage($g_hGraphic, $g_hImage, 40, 25)
	_WinAPI_RedrawWindow($g_hGUI, 0, 0, $RDW_VALIDATE)

	Return $GUI_RUNDEFMSG
EndFunc   ;==>MY_WM_PAINT


;----Compile progress bar counter
Func progressbar1()
	Local $i = GUICtrlRead($progress)
	$i += 1
	If $i > 99 Then $i = 0
	GUICtrlSetData($progress, $i)
EndFunc   ;==>progressbar1

;----Decompile progress bar counter
Func progressbar2()
	Local $i = GUICtrlRead($progress)
	$i += 1
	If $i > 99 Then $i = 0
	GUICtrlSetData($progress, $i)
EndFunc   ;==>progressbar2

Func ClearEdit()
    GUICtrlSetData($g_hLog, "")
	GUICtrlSetData($g_hLog, ">>> Log cleared... Ready" & @CRLF, 1)
EndFunc

; Function to add a diagnostic message to the array
Func _AddDiagnosticMessage($sMessage)
	;FileWrite($hLog, $sMessage & @CRLF)
	_ArrayAdd($aDiagnosticMessages, $sMessage) ; Use _ArrayAdd() to add the message to the array
EndFunc

;----TexturePackager Version Date Formatter
Func FormatDate($date)
    If Not IsArray($date) Or UBound($date) < 3 Then
        MsgBox($MB_SYSTEMMODAL, "", "Date format error")
        Return False
    EndIf
    Return $date[1] & "-" & $date[2] & "-" & $date[0]
EndFunc

;----Deletes files from temp folder on app exit
Func CleanupFiles()
    Local $tempFolder = "C:\temp\"

Local $filesToDelete[9] = ["base.exe", "D3DX9_43.dll", "kodi.png", "msvcp140.dll", _
                           "msvcp140.dll", "TexturePacker.exe", "update.txt", "VCRUNTIME140.dll", "vcruntime140.dll"]

    For $i = 0 To UBound($filesToDelete) - 1
        Local $filePath = $tempFolder & $filesToDelete[$i]
        If FileExists($filePath) Then
            Local $hFile = FileOpen($filePath, 0) ; Open the file for reading to check if it's locked
            If $hFile = -1 Then
                FileClose($hFile) ; Close the file handle
            Else
                FileDelete($filePath) ; Delete the file
            EndIf
        EndIf
    Next
	;----This has to be force deleted, check file attributes, workaround for now
	$command = 'del "C:\temp\kodi.png"'
	Run(@ComSpec & " /c " & $command, "C:\temp", @SW_HIDE)
EndFunc

;----TexturePackager Engineering Size Formatter
Func ByteSuffix($iBytes)
        Local $iIndex = 0, $aArray = ['bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
        While $iBytes > 1023
                $iIndex += 1
                $iBytes /= 1024
        WEnd
        Return Round($iBytes) & $aArray[$iIndex]
EndFunc   ;==>ByteSuffix

;----Enables Dev mode when user enter specific keyboard sequence
Func enable_dev()
	GUICtrlSetState($dev, $GUI_ENABLE)
EndFunc   ;==>enable_dev

;----Internet update of the program routine (WIP)
Func update()
	FileDelete("C:\temp" & "\update.exe")
	FileDelete("C:\temp" & "\update.txt")
	FileDelete("C:\temp" & "\update.bat")
	gettime()
	FileWrite($hLog, $short & ": " & 'Automatic software update started - Connecting to server...' & @CRLF)
	GUICtrlSetData($g_hLog, $short & ": " & 'Automatic software update started - Connecting to server...' & @CRLF, 1)
	$online = _INetGetSource("")
	FileWrite("C:\temp" & "\update.txt", $online)
	GUICtrlSetData($g_hLog, " " & @CRLF, 1) ; TODO
	$latest = FileReadLine("C:\temp" & "\update.txt", 1)
	If $latest <> "" Then
		If $version <> $latest Then
			Traytip("Kodi - Texture Tool", "New update available !",2,1)
			FileWrite($hLog, $short & ": " & 'Update found.' & @CRLF)
			GUICtrlSetData($g_hLog, $short & ": " & 'Update found.' & @CRLF, 1)
			$updater = GUICreate("Kodi - Texture Tool (Updater)", 320, 65)
			$progress2 = GUICtrlCreateProgress(10, 10, 300, 15)
			$Button = GUICtrlCreateButton("Download", 60, 35, 200, 25)
			GUISetState()
			$URL = ""
			$FileName = "C:\temp" & "\update.exe"
		Else
			gettime()
			FileWrite($hLog, $short & ": " & "No update found!" & @CRLF)
			GUICtrlSetData($g_hLog, $short & ": " & "No update found!" & @CRLF, 1)
			TrayTip("Kodi - Texture Tool", "Texture Tool - v." & $version & " (latest)", 2, 1)
			$Button = ""
			gui() ; Why are we respawning new versions of the GUI when we havne't updated ? ? ?

		EndIf
		FileDelete("C:\temp" & "\update.txt")
		Sleep(300)
	Else
		gettime()
		FileWrite($hLog, $short & ": " & "No response from server - Check internet connection - (WIP) Function has been temporarily disabled" & @CRLF)
		GUICtrlSetData($g_hLog, $short & ": " & "No response from server - Check internet connection - (WIP) Function has been temporarily disabled" & @CRLF, 1)
		;TrayTip("Update server unavailable", "Cannot reach update host, check again later", 2, 1)
		TrayTip("Update Function Working", "Active updates disabled. No updates available. (WIP) Functional server to rollout updates.", 2, 1)
		gui() ; Why are we respawning new versions of the GUI when we havne't updated ? ? ?
	EndIf

	While Sleep(10)
		$nMsg = GUIGetMsg()
		If $nMsg == $GUI_EVENT_CLOSE Then
			Exit
		ElseIf $nMsg == $Button Then
			FileWrite($hLog, $short & ": " & 'Downloading Update.' & @CRLF)
			GUICtrlSetData($g_hLog, $short & ": " & 'Downloading Update.' & @CRLF, 1)
			If InetGetSize($URL) > 0 Then ;when the file is downloaded
				If $Download Then ;when the file is downloaded
					$Download = False
					InetClose($File)
					FileDelete($FileName)
					GUICtrlSetData($progress2, 0)
					GUICtrlSetData($Button, "Download")
				Else
					$Download = True
					$File = InetGet($URL, $FileName, 1, 1)
					GUICtrlSetData($Button, "Abort")
				EndIf
			EndIf
		EndIf

		If $Download Then ;when the file is downloaded
			$info = InetGetInfo($File) ;Information about the current download ($File)
			GUICtrlSetData($progress2, $info[0] * 100 / $info[1]) ;percentage progress of the download

			If $info[2] Then ;when the file has been completely downloaded
				FileWrite($hLog, $short & ": " & 'Update done.' & @CRLF)
				GUICtrlSetData($g_hLog, $short & ": " & 'Update done.' & @CRLF, 1)
				InetClose($File)
				$Download = False
				GUICtrlSetData($Button, "Download complete!")
				sleep(2000)
				FileWrite("C:\temp" & "\update.bat", "ping -n 2 127.0.0.1 > NUL" & @CRLF & "del " & '"' & @ScriptFullPath & '"' & @CRLF & _
						  "ping -n 2 127.0.0.1 > NUL" & @CRLF & "ren " & "C:\temp" & "\update.exe" & " " & '"' & @ScriptName & '"' & @CRLF & _
						  "ping -n 2 127.0.0.1 > NUL" & @CRLF & "move " & '"' & "C:\temp" & "\" & @ScriptName & '"' & " " & '"' & @ScriptFullPath & '"')
				GUICtrlSetData($g_hLog, " " & @CRLF, 1) ; TODO
				GUICtrlSetData($Button, "Installing update!")
				ShellExecute("C:\temp" & "\update.bat", "", "", "", @SW_HIDE)
				Exit
			EndIf
		EndIf
	WEnd
EndFunc   ;==>update

;----Get system clock returns long or short version
Func gettime()
	$time = @YEAR & "." & @MON & "." & @MDAY & "-" & @HOUR & ":" & @MIN & ":" & @SEC
	$short = @HOUR & ":" & @MIN & ":" & @SEC
EndFunc   ;==>gettime

