-- Export one Photos album to a folder. Called by deploy/photos-sync.sh.
--
--   osascript export-album.applescript "Mantel" "/tmp/stage"
--
-- Prints "exported <n>", or a line starting with "error:" that the shell turns
-- into something a human can act on.

on run argv
	set albumName to item 1 of argv
	set stagePath to item 2 of argv
	set stageFolder to POSIX file stagePath as alias

	tell application "Photos"
		-- A missing album is the usual first-run mistake, and worth its own
		-- message rather than a raw AppleScript error number.
		if not (exists album albumName) then
			return "error: no album named " & albumName
		end if

		set theItems to media items of album albumName
		set total to count of theItems
		if total is 0 then
			return "exported 0"
		end if

		-- Originals keep the capture date and the untouched pixels.
		try
			export theItems to stageFolder with using originals
			return "exported " & total
		end try

		-- With iCloud's "Optimise Mac Storage" the original may not be on this
		-- Mac; take whatever Photos can render locally instead.
		try
			export theItems to stageFolder
			return "exported " & total
		end try

		-- A single unreadable item fails a whole-album export, so the last
		-- resort is one at a time, letting the rest through.
		set exported to 0
		repeat with anItem in theItems
			try
				export {anItem} to stageFolder with using originals
				set exported to exported + 1
			on error
				try
					export {anItem} to stageFolder
					set exported to exported + 1
				end try
			end try
		end repeat
		return "exported " & exported
	end tell
end run
