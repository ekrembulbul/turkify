-- Turkify — Hammerspoon entegrasyonu (Faz 1)
--
-- Hyper + T (Ctrl+Alt+Cmd+T) ile seçili metni Türkçe diakritiklerle düzeltir.
-- Akış: seçimi kopyala → düzeltme motorunu çalıştır → sonucu yapıştır →
-- panoyu (clipboard) eski haline döndür. Hata/zaman aşımında orijinal metin
-- bozulmadan kullanıcıya bildirim verilir.
--
-- Kurulum: bu dosyayı ~/.hammerspoon/init.lua içinden require/dofile edin, örn.
--   dofile(os.getenv("HOME") .. "/projects/turkify/hammerspoon/turkify.lua")

local turkify = {}

-- ── Yapılandırma ──────────────────────────────────────────────────────────
local PYTHON = os.getenv("HOME") .. "/projects/turkify/.venv/bin/python"
local MODULE = "turkify"
local HOTKEY_MODS = { "ctrl", "alt", "cmd" } -- Hyper
local HOTKEY_KEY = "t"
local ENGINE_TIMEOUT_SEC = 5 -- motor takılırsa iptal süresi
local COPY_WAIT_MAX_MS = 500 -- seçimin panoya düşmesi için azami bekleme
local COPY_POLL_MS = 20
local CLIPBOARD_RESTORE_DELAY_SEC = 0.4 -- yapıştırma tamamlansın diye

-- ── Yardımcılar ─────────────────────────────────────────────────────────────
local function notify(message)
	hs.notify.new({ title = "Turkify", informativeText = message }):send()
end

local function writeTempFile(contents)
	local path = os.tmpname()
	local file, err = io.open(path, "wb")
	if not file then
		return nil, err
	end
	file:write(contents)
	file:close()
	return path
end

-- Düzeltme motorunu çalıştırır; sonucu (veya hatayı) callback ile döndürür.
local function runEngine(inputText, onResult)
	local tmpPath, writeErr = writeTempFile(inputText)
	if not tmpPath then
		onResult(nil, "Geçici dosya yazılamadı: " .. tostring(writeErr))
		return
	end

	local finished = false
	local task = hs.task.new(PYTHON, function(exitCode, stdOut, stdErr)
		if finished then
			return
		end
		finished = true
		os.remove(tmpPath)
		if exitCode == 0 then
			onResult(stdOut, nil)
		else
			onResult(nil, "Motor hatası (kod " .. tostring(exitCode) .. "): " .. tostring(stdErr))
		end
	end, { "-m", MODULE, tmpPath })

	task:start()

	-- Zaman aşımı koruması: hs.task'ın yerleşik timeout'u yoktur.
	hs.timer.doAfter(ENGINE_TIMEOUT_SEC, function()
		if not finished then
			finished = true
			task:terminate()
			os.remove(tmpPath)
			onResult(nil, "Motor zaman aşımına uğradı (" .. ENGINE_TIMEOUT_SEC .. " sn).")
		end
	end)
end

-- Seçimi kopyalar; pano değişene kadar (azami COPY_WAIT_MAX_MS) bekler.
local function copySelection(onCopied)
	local original = hs.pasteboard.getContents()
	local beforeCount = hs.pasteboard.changeCount()

	hs.eventtap.keyStroke({ "cmd" }, "c")

	local waited = 0
	local timer
	timer = hs.timer.doEvery(COPY_POLL_MS / 1000, function()
		waited = waited + COPY_POLL_MS
		if hs.pasteboard.changeCount() ~= beforeCount then
			timer:stop()
			onCopied(hs.pasteboard.getContents(), original)
		elseif waited >= COPY_WAIT_MAX_MS then
			timer:stop()
			onCopied(nil, original) -- seçim yok / kopyalanamadı
		end
	end)
end

local function pasteResult(corrected, originalClipboard)
	hs.pasteboard.setContents(corrected)
	hs.eventtap.keyStroke({ "cmd" }, "v")
	-- Yapıştırma tamamlandıktan sonra kullanıcının panosunu geri yükle.
	hs.timer.doAfter(CLIPBOARD_RESTORE_DELAY_SEC, function()
		if originalClipboard ~= nil then
			hs.pasteboard.setContents(originalClipboard)
		end
	end)
end

-- ── Ana akış ────────────────────────────────────────────────────────────────
function turkify.correctSelection()
	copySelection(function(selected, originalClipboard)
		if selected == nil or selected == "" then
			notify("Seçili metin bulunamadı.")
			if originalClipboard ~= nil then
				hs.pasteboard.setContents(originalClipboard)
			end
			return
		end

		runEngine(selected, function(corrected, err)
			if err ~= nil or corrected == nil then
				notify(err or "Bilinmeyen hata.")
				if originalClipboard ~= nil then
					hs.pasteboard.setContents(originalClipboard)
				end
				return
			end
			pasteResult(corrected, originalClipboard)
		end)
	end)
end

hs.hotkey.bind(HOTKEY_MODS, HOTKEY_KEY, turkify.correctSelection)

return turkify
