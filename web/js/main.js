// Глобальные переменные
let currentLanguage = 'ru'
let locale = {}
let config = {}
let currentStats = {}
let modalCallback = null
let systemInfoGlobal = null

// --- Модули (если потребуется разделение) ---
// Можно вынести мониторинг, очистку, оптимизацию и автозагрузку в отдельные файлы и подключить через import или <script> (если не нужен IE11).
// Например: import { startMonitoring } from './monitor.js'

// --- Инициализация приложения ---
window.onload = async () => {
	try {
		// Загрузка конфигурации
		config = await eel.get_config()()

		// Безопасная инициализация checkUpdatesOnStart
		if (typeof config.checkUpdatesOnStart === 'undefined') {
			config.checkUpdatesOnStart = false
		}

		// Установка темы
		const themeToggle = document.getElementById('theme-toggle')
		const themeLabel = document.getElementById('theme-label')
		if (themeToggle && themeLabel) {
			document.body.classList.toggle('light', config.theme === 'light')
			themeToggle.checked = config.theme === 'light'
			themeLabel.textContent =
				config.theme === 'light'
					? locale.lightTheme || 'Светлая'
					: locale.darkTheme || 'Тёмная'
		}

		// Установка настроек трея и автозапуска
		const trayToggle = document.getElementById('tray-toggle')
		const autorunToggle = document.getElementById('autorun-toggle')
		if (trayToggle) trayToggle.checked = !!config.tray
		if (autorunToggle) autorunToggle.checked = !!config.autorun

		// Установка языка
		const langSelect = document.getElementById('language-select')
		const settingsLang = document.getElementById('settings-language')
		if (langSelect) langSelect.value = config.language
		if (settingsLang) settingsLang.value = config.language
		currentLanguage = config.language

		// Загрузка локализации
		await loadLocale()
		updateUIWithLocale()

		// Загрузка информации о системе (в том числе модель процессора)
		await loadSystemInfo()
		// Сохраняем для дальнейшего использования
		systemInfoGlobal = await eel.get_system_info()()
		updateCpuModel()

		// --- Исправлено: звук загрузки воспроизводится сразу ---
		playSplashSound()

		// --- Исправлено: анимация загрузки не менее 1.5 сек ---
		const splashStart = Date.now()
		await Promise.all([
			initSplashScreen(),
			// Параллельно грузим данные для главной
			loadSystemInfo(),
		])
		const splashElapsed = Date.now() - splashStart
		const minSplash = 1500
		if (splashElapsed < minSplash) {
			await new Promise(res => setTimeout(res, minSplash - splashElapsed))
		}

		// Завершение загрузки
		document.getElementById('splash').classList.add('fade-out')
		setTimeout(() => {
			document.getElementById('splash').style.display = 'none'
			document.getElementById('app').style.opacity = '1'
			showTab('home')
			showNotification(locale.welcome || 'Добро пожаловать в Fixer!', true)
		}, 500)

		// --- Исправлено: запуск мониторинга ---
		startMonitoring()

		// Проверка обновлений при запуске
		if (config.checkUpdatesOnStart) {
			checkUpdates()
		}
	} catch (e) {
		console.error('Ошибка инициализации приложения:', e)
		const splash = document.getElementById('splash')
		const app = document.getElementById('app')
		if (splash) splash.style.display = 'none'
		if (app) app.style.opacity = '1'
		showNotification('Ошибка запуска приложения', false)
	}
}

// --- Локализация ---
async function loadLocale() {
	try {
		locale = await eel.get_locale(currentLanguage)()
	} catch (e) {
		console.error('Error loading locale:', e)
		locale = {}
	}
}

function updateUIWithLocale() {
	// Обновляем все элементы с data-locale
	document.querySelectorAll('[data-locale]').forEach(el => {
		const key = el.getAttribute('data-locale')
		if (locale[key]) {
			if (el.tagName === 'OPTION') el.textContent = locale[key]
			else el.innerHTML = locale[key]
		}
	})
	// Обновляем другие элементы (например, theme-select)
	const themeSelect = document.getElementById('theme-select')
	if (themeSelect) {
		themeSelect.value = config.theme || 'dark'
	}
}

async function changeLanguage(lang) {
	currentLanguage = lang
	await loadLocale()
	updateUIWithLocale()
	showNotification(locale.languageChanged || 'Язык изменен')
}

// --- Splash screen (анимация) ---
async function initSplashScreen() {
	let progress = 0
	const progressBar = document.getElementById('splash-progress')
	return new Promise(resolve => {
		const progressInterval = setInterval(() => {
			progress += Math.random() * 4 + 2 // Медленнее
			if (progress >= 100) {
				progress = 100
				clearInterval(progressInterval)
				resolve()
			}
			if (progressBar) progressBar.style.width = `${progress}%`
		}, 80)
	})
}

// --- Навигация ---
function showTab(id) {
	// Обновляем активную кнопку в сайдбаре
	document.querySelectorAll('aside button').forEach(btn => {
		btn.classList.remove('active')
	})
	document.getElementById(`${id}-btn`).classList.add('active')

	// Показываем выбранную вкладку
	document.querySelectorAll('.tab').forEach(tab => {
		tab.classList.add('hidden')
	})
	document.getElementById(id).classList.remove('hidden')

	// Загружаем данные для вкладки при необходимости
	switch (id) {
		case 'opt':
			loadServices()
			break
		case 'clean':
			loadCacheSizes()
			break
		case 'startup':
			loadStartupApps()
			break
	}

	// Воспроизводим звук клика
	playClickSound()
}

// --- Мониторинг (реализация с круговой анимацией) ---
function startMonitoring() {
	updateStats()
	setInterval(updateStats, 2000)
}

async function updateStats() {
	const stats = await eel.get_stats()()
	if (!stats) return

	// CPU
	const cpuPercent = stats.cpu?.percent || 0
	const cpuCores = stats.cpu?.cores || 0
	const cpuThreads = stats.cpu?.threads || 0
	const cpuFreq = stats.cpu?.freq?.current || 0
	const cpuTemp = stats.temperature?.cpu || 0

	setText('sidebar-cpu', `${cpuPercent}%`)
	setText('home-cpu', `${cpuPercent}%`)
	setText('cpu-value', `${cpuPercent}%`)
	setText('cpu-cores', `${cpuCores}/${cpuThreads}`)
	setText('cpu-freq', `${cpuFreq} MHz`)
	setText('cpu-temp', `${cpuTemp}°C`)
	drawCircleGauge('cpu-gauge-canvas', cpuPercent, '#7c4dff', '#2e2e2e')

	// RAM
	const ramPercent = stats.ram?.percent || 0
	const ramTotal = stats.ram?.total || 0
	const ramUsed = stats.ram?.used || 0
	const ramFree = stats.ram?.available || 0

	setText('sidebar-ram', `${ramPercent}%`)
	setText('home-ram', `${ramPercent}%`)
	setText('ram-value', `${ramPercent}%`)
	setText('ram-total', formatBytes(ramTotal))
	setText('ram-used', formatBytes(ramUsed))
	setText('ram-free', formatBytes(ramFree))
	drawCircleGauge('ram-gauge-canvas', ramPercent, '#00e5ff', '#2e2e2e')

	updateCpuModel()
	updateFirewallStatus()
}

// --- Круговой прогрессбар (canvas) ---
function drawCircleGauge(canvasId, percent, color, bgColor) {
	const canvas = document.getElementById(canvasId)
	if (!canvas) return
	const ctx = canvas.getContext('2d')
	const size = canvas.width
	const lineWidth = 12
	const radius = (size - lineWidth) / 2
	ctx.clearRect(0, 0, size, size)
	// Фон
	ctx.beginPath()
	ctx.arc(size / 2, size / 2, radius, 0, 2 * Math.PI)
	ctx.strokeStyle = bgColor
	ctx.lineWidth = lineWidth
	ctx.stroke()
	// Прогресс
	const startAngle = -Math.PI / 2
	const endAngle = startAngle + (2 * Math.PI * Math.min(percent, 100)) / 100
	ctx.beginPath()
	ctx.arc(size / 2, size / 2, radius, startAngle, endAngle)
	ctx.strokeStyle = color
	ctx.lineWidth = lineWidth
	ctx.lineCap = 'round'
	ctx.stroke()
}

// --- Модель процессора (только модель) ---
function extractCpuModel(raw) {
	if (!raw) return ''
	// Пример: "AMD Ryzen 7 7730U with Radeon Graphics" -> "AMD Ryzen 7 7730U"
	const match = raw.match(/(Intel|AMD)[^@,]+/)
	return match ? match[0].trim() : raw.split('@')[0].trim()
}

function updateCpuModel() {
	const cpuModel =
		systemInfoGlobal && systemInfoGlobal.processor
			? extractCpuModel(systemInfoGlobal.processor)
			: ''
	const elMon = document.getElementById('cpu-model-monitor')
	if (elMon) elMon.textContent = cpuModel
}

// --- Проверка состояния функций (пример: брандмауэр) ---
async function updateFirewallStatus() {
	const res = await eel.get_firewall_status()()
	const el = document.getElementById('firewall-status')
	const toggle = document.getElementById('firewall-toggle')
	if (el && res && typeof res.enabled !== 'undefined') {
		el.textContent = res.enabled ? 'Включён' : 'Выключен'
		el.style.color = res.enabled ? '#4caf50' : '#ff5252'
	}
	if (toggle && res && typeof res.enabled !== 'undefined') {
		toggle.checked = res.enabled
	}
}

function setText(id, text) {
	const el = document.getElementById(id)
	if (el) el.textContent = text
}

function updateGauge(id, percent) {
	const el = document.getElementById(id)
	if (el) {
		const angle = (Math.min(percent, 100) / 100) * 180
		el.style.transform = `rotate(${angle}deg)`
	}
}

function updateDisks(disks) {
	const container = document.getElementById('disks-container')
	if (!container) return
	container.innerHTML = ''
	disks.forEach(disk => {
		const div = document.createElement('div')
		div.className = 'disk-card'
		div.innerHTML = `
			<div class="disk-header">
				<span class="disk-name">${disk.device || disk.mountpoint}</span>
				<span class="disk-percent">${disk.percent}%</span>
			</div>
			<div class="disk-bar">
				<div class="disk-progress" style="width:${disk.percent}%;"></div>
			</div>
			<div class="disk-details">
				<span>Всего: ${formatBytes(disk.total)}</span>
				<span>Свободно: ${formatBytes(disk.free)}</span>
			</div>
		`
		container.appendChild(div)
	})
}

// --- Уведомления ---
function showNotification(message, isSuccess = true) {
	if (!config.notifications) return

	const notif = document.getElementById('notification')
	if (!notif) return

	notif.className = isSuccess ? 'show' : 'show error'
	notif.querySelector('.notification-message').textContent = message

	// Автоматическое скрытие
	setTimeout(() => {
		hideNotification()
	}, 3000)

	// Воспроизведение звука
	if (config.sound) {
		playNotificationSound()
	}
}

function hideNotification() {
	const notif = document.getElementById('notification')
	if (notif) {
		notif.classList.remove('show', 'error')
	}
}

// --- Модальные окна ---
function showModal(title, message, confirmText, callback) {
	modalCallback = callback

	document.getElementById('modal-title').textContent = title
	document.getElementById('modal-body').textContent = message
	document.getElementById('modal-confirm').textContent = confirmText

	document.getElementById('modal').classList.add('show')
}

function closeModal() {
	document.getElementById('modal').classList.remove('show')
	modalCallback = null
}

function confirmModal() {
	if (modalCallback) {
		modalCallback()
	}
	closeModal()
}

// --- Звуки ---
function playSplashSound() {
	if (!config.sound) return

	const audio = document.getElementById('splash-audio')
	if (audio) {
		audio.volume = 0.3
		audio.play().catch(e => console.log('Splash audio error:', e))
	}
}

function playNotificationSound() {
	if (!config.sound) return

	const audio = document.getElementById('notif-audio')
	if (audio) {
		audio.volume = 0.2
		audio.play().catch(e => console.log('Notification audio error:', e))
	}
}

function playClickSound() {
	if (!config.sound) return

	const audio = document.getElementById('click-audio')
	if (audio) {
		audio.volume = 0.1
		audio.currentTime = 0
		audio.play().catch(e => console.log('Click audio error:', e))
	}
}

// --- Глобальный делегат для клика по кнопкам ---
document.addEventListener('click', function (e) {
	if (e.target.closest('button')) playClickSound()
})

// --- Обновление приложения ---
async function checkUpdates(manual = false) {
	const updateInfo = await eel.check_updates()()

	if (updateInfo.update_available) {
		showModal(
			locale.updateAvailable || 'Доступно обновление',
			`${locale.newVersionAvailable || 'Доступна новая версия'} ${
				updateInfo.latest_version
			}. ${locale.currentVersion || 'Текущая версия'}: ${
				updateInfo.current_version
			}`,
			locale.update || 'Обновить',
			() => {
				// Открываем страницу релиза в браузере
				window.open(updateInfo.release_url, '_blank')
			}
		)
	} else if (manual) {
		showNotification(locale.noUpdatesAvailable || 'Обновлений не найдено', true)
	}
}

// --- Системная информация ---
async function loadSystemInfo() {
	const systemInfo = await eel.get_system_info()()
	const container = document.getElementById('system-info')

	if (systemInfo && container) {
		container.innerHTML = ''

		const infoMap = {
			os: locale.operatingSystem || 'Операционная система',
			os_version: locale.osVersion || 'Версия ОС',
			os_release: locale.osRelease || 'Релиз ОС',
			architecture: locale.architecture || 'Архитектура',
			processor: locale.processor || 'Процессор',
			hostname: locale.hostname || 'Имя компьютера',
			ip: locale.ipAddress || 'IP-адрес',
			ram: locale.totalRAM || 'Всего RAM',
		}

		for (const [key, label] of Object.entries(infoMap)) {
			if (systemInfo[key]) {
				const item = document.createElement('div')
				item.className = 'info-item'

				const labelEl = document.createElement('span')
				labelEl.className = 'info-label'
				labelEl.textContent = label

				const valueEl = document.createElement('span')
				valueEl.className = 'info-value'

				// Форматирование значений
				let value = systemInfo[key]
				if (key === 'ram') {
					value = `${value} GB`
				}

				valueEl.textContent = value

				item.appendChild(labelEl)
				item.appendChild(valueEl)
				container.appendChild(item)
			}
		}
	}
	// Сохраняем глобально
	systemInfoGlobal = systemInfo
	updateCpuModel()
}

// --- Автозагрузка ---
async function loadStartupApps() {
	const apps = await eel.get_startup_apps()()
	const list = document.getElementById('startup-list')
	if (!list) return
	list.innerHTML = ''
	let enabledCount = 0
	apps.forEach(app => {
		if (app.enabled) enabledCount++
		const div = document.createElement('div')
		div.className = 'startup-item'
		div.innerHTML = `
			<div class="startup-info">
				<div class="startup-name">${app.name}
					<span class="startup-type ${app.type === 'system' ? 'system' : ''}">${
			app.type
		}</span>
				</div>
				<div class="startup-path">${app.path}</div>
			</div>
			<div class="startup-actions">
				<label class="switch">
					<input type="checkbox" ${
						app.enabled ? 'checked' : ''
					} onchange="toggleStartupApp('${app.name}','${
			app.type
		}',this.checked)">
					<span class="slider"></span>
				</label>
				<button class="btn-delete" onclick="deleteStartupApp('${app.name}','${
			app.type
		}')"><i class="fas fa-trash"></i></button>
			</div>
		`
		list.appendChild(div)
	})
	setText('startup-count', `${apps.length} программ`)
	setText('startup-enabled', `${enabledCount} включено`)
}

async function toggleStartupApp(name, type, enabled) {
	await eel.toggle_startup_app(name, type, enabled)()
	loadStartupApps()
}

async function deleteStartupApp(name, type) {
	await eel.delete_startup_app(name, type)()
	loadStartupApps()
}

function filterStartup() {
	const input = document.getElementById('startup-search')
	const filter = input.value.toLowerCase()
	const items = document.querySelectorAll('.startup-item')
	items.forEach(item => {
		const name = item.querySelector('.startup-name').textContent.toLowerCase()
		item.style.display = name.includes(filter) ? '' : 'none'
	})
}

function refreshStartup() {
	loadStartupApps()
}

// --- Ключевые службы: список и переключатели ---
async function loadServices() {
	const services = await eel.get_services()()
	const list = document.getElementById('services-list')
	if (!list) return
	list.innerHTML = ''
	services.forEach(srv => {
		const div = document.createElement('div')
		div.className = 'optimization-item'
		div.innerHTML = `
			<div class="optimization-info">
				<h4>${srv.displayName}</h4>
				<p>${srv.description}</p>
			</div>
			<label class="switch">
				<input type="checkbox" ${
					srv.enabled ? 'checked' : ''
				} onchange="toggleService('${srv.name}',this.checked)">
				<span class="slider"></span>
			</label>
			<span style="margin-left:10px;font-size:13px;color:var(--text-secondary);">${
				srv.enabled ? 'Включена' : 'Отключена'
			}</span>
		`
		list.appendChild(div)
	})
}

async function toggleService(name, enabled) {
	await eel.toggle_service(name, enabled)()
	loadServices()
}

// --- Очистка кэша: показывать только найденные ---
async function loadCacheSizes() {
	const sizes = await eel.get_cache_sizes()()
	const list = document.getElementById('cache-list')
	if (!list) return
	list.innerHTML = ''
	const cacheApps = [
		{ key: 'Chrome', label: 'Google Chrome' },
		{ key: 'Edge', label: 'Microsoft Edge' },
		{ key: 'Firefox', label: 'Mozilla Firefox' },
		{ key: 'Discord', label: 'Discord' },
		{ key: 'Temp', label: 'Temp' },
		{ key: 'Prefetch', label: 'Prefetch' },
	]
	cacheApps.forEach(app => {
		if (sizes[app.key] !== undefined) {
			const div = document.createElement('div')
			div.className = 'clean-item'
			div.innerHTML = `
				<div class="clean-info">
					<h4>${app.label}</h4>
					<p>Очистка кэша приложения</p>
					<div class="clean-details">Размер: ${sizes[app.key]} MB</div>
				</div>
				<button class="btn-clean" onclick="clearCache('${app.key}')">Очистить</button>
			`
			list.appendChild(div)
		}
	})
}

// --- Тема ---
function toggleTheme(theme) {
	document.body.classList.remove('light', 'rgb')
	if (theme === 'light') document.body.classList.add('light')
	if (theme === 'rgb') document.body.classList.add('rgb')
	config.theme = theme
	eel.update_config(config)
	showNotification(
		theme === 'light'
			? locale.lightThemeEnabled || 'Светлая тема включена'
			: theme === 'rgb'
			? locale.rgbThemeEnabled || 'RGB тема включена'
			: locale.darkThemeEnabled || 'Тёмная тема включена'
	)
}

// --- Настройки ---
function updateLanguageSetting(lang) {
	config.language = lang
	eel.update_config(config)
	changeLanguage(lang)
}

function updateNotificationsSetting(enabled) {
	config.notifications = enabled
	eel.update_config(config)
	showNotification(
		enabled
			? locale.notificationsEnabled || 'Уведомления включены'
			: locale.notificationsDisabled || 'Уведомления выключены'
	)
}

function updateSoundSetting(enabled) {
	config.sound = enabled
	eel.update_config(config)
	showNotification(
		enabled
			? locale.soundsEnabled || 'Звуки включены'
			: locale.soundsDisabled || 'Звуки выключены'
	)
}

function updateTraySetting(enabled) {
	config.tray = enabled
	eel.update_config(config)
	showNotification(enabled ? 'Добавлено в трей' : 'Убрано из трея')
}

function updateAutorunSetting(enabled) {
	config.autorun = enabled
	eel.update_config(config)
	eel.set_autorun(enabled)()
	showNotification(enabled ? 'Автозапуск включён' : 'Автозапуск выключен')
}

// --- Общие функции ---
function formatBytes(bytes, decimals = 2) {
	if (bytes === 0) return '0 Bytes'

	const k = 1024
	const dm = decimals < 0 ? 0 : decimals
	const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']
	const i = Math.floor(Math.log(bytes) / Math.log(k))

	return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i]
}

function formatSpeed(kb) {
	if (kb < 1024) {
		return kb.toFixed(1) + ' KB/s'
	} else {
		return (kb / 1024).toFixed(1) + ' MB/s'
	}
}

// --- Экспортируем функции для использования в других модулях ---
window.showNotification = showNotification
window.showModal = showModal
window.playClickSound = playClickSound
window.formatBytes = formatBytes
window.formatSpeed = formatSpeed
window.showTab = showTab
window.loadSystemInfo = loadSystemInfo
window.toggleStartupApp = toggleStartupApp
window.deleteStartupApp = deleteStartupApp
window.filterStartup = filterStartup
window.refreshStartup = refreshStartup
window.updateTraySetting = updateTraySetting
window.updateAutorunSetting = updateAutorunSetting
window.toggleService = toggleService
window.loadServices = loadServices
