(function () {
    Telegram.WebApp.ready();
    Telegram.WebApp.expand();
    Telegram.WebApp.enableClosingConfirmation();

    const i18n = {
        "en": {
            "close": "Close",
            "word": "Word",
            "not_host": "You`re not the host",
            "ended": "Game ended",
            "not_auth": "No authorization",
            "already_connected": "The host is already connected",
            "error": "Error"
        },
        "ru": {
            "close": "Закрыть",
            "word": "Слово",
            "not_host": "Вы не ведущий",
            "ended": "Игра закончилась",
            "not_auth": "Нет авторизации",
            "already_connected": "Ведущий уже подключен",
            "error": "Ошибка"
        },
    };

    const default_locale = "en";
    let current_locale = window.navigator.language.split("-")[0];
    if (current_locale in i18n === false) current_locale = default_locale;

    _ = (key) => { return i18n[current_locale][key] ?? key; };

    const initData = Telegram.WebApp.initData;
    const initDataUnsafe = Telegram.WebApp.initDataUnsafe;

    if (!initData || !initDataUnsafe || !initDataUnsafe.start_param) {
        showFullBlockingMessage(_('not_auth'));
        return;
    }

    // gameId__123d234f
    const gameId = initDataUnsafe.start_param;

    current_locale = initDataUnsafe.user?.language_code ?? current_locale;

    Telegram.WebApp.MainButton
        .setText(_('close'))
        .show()
        .onClick(() => { Telegram.WebApp.close(); });

    const canvas = document.getElementById('paintarea'),
        vcanvas = document.createElement('canvas'),
        ctx = canvas.getContext('2d'),
        vctx = vcanvas.getContext('2d'),

        colorPalleteBtn = document.getElementById('color'),

        smallDotBtn = document.getElementById('small-dot'),
        mediumDotBtn = document.getElementById('medium-dot'),
        largeDotBtn = document.getElementById('large-dot'),
        eraserBtn = document.getElementById('eraser'),

        clearBtn = document.getElementById('clear'),
        wordBtn = document.getElementById('word'),

        publishImagePadding = 18;

    let drawingWord = null,
        rawBrushData = [],
        drawing = false,
        dirty = false,
        paintSize = 3,
        color = '#000000',
        prevColor = null,
        eraserSize = 12,
        eraserColor = '#ffffff',
        currentTool = 'painter',
        selectedBtn = null,
        drawingBoundary = null;

    onDrawToolSelected('painter', smallDotBtn, 3);
    attachCanvasListeners();

    let eventSource = subscribeToGameEvents();
    let intervalHandle = setInterval(() => publishImage(), 1_500);

    function attachCanvasListeners() {
        // Try to not fire slide down event:
        // https://stackoverflow.com/questions/76842573/a-bug-with-collapsing-when-scrolling-in-web-app-for-telegram-bot
        document.addEventListener('touchmove', (e) => { e.preventDefault() }, { passive: false });

        smallDotBtn.onclick = () => { onDrawToolSelected('painter', smallDotBtn, 3); };
        mediumDotBtn.onclick = () => { onDrawToolSelected('painter', mediumDotBtn, 6); };
        largeDotBtn.onclick = () => { onDrawToolSelected('painter', largeDotBtn, 12); };
        eraserBtn.onclick = () => { onEraserSelected(); };

        clearBtn.onclick = clearCanvas;
        wordBtn.onclick = showWord;
        colorPalleteBtn.onchange = (e) => { color = e.target.value };

        // Drawing event handlers (bound to mouse, redirected from touch)
        canvas.addEventListener('mousedown', onMouseDown, false);
        canvas.addEventListener('mouseup', onMouseUp, false);
        canvas.addEventListener('mousemove', onMouseMove, false);

        // Touch event redirect
        canvas.addEventListener('touchstart', onTouchStart, false);
        canvas.addEventListener('touchend', onTouchEnd, false);
        canvas.addEventListener('touchcancel', onTouchEnd, false);
        canvas.addEventListener('touchmove', onTouchMove, false);

        // Dynamic canvas size
        window.addEventListener('resize', resizeCanvas, false);
        window.addEventListener('load', init, false);
    }

    function detachListeners() {
        smallDotBtn.onclick = null;
        mediumDotBtn.onclick = null;
        largeDotBtn.onclick = null;
        eraserBtn.onclick = null;

        clearBtn.onclick = null;
        wordBtn.onclick = null;
        colorPalleteBtn.onchange = null;

        canvas.removeEventListener('mousedown', onMouseDown, false);
        canvas.removeEventListener('mouseup', onMouseUp, false);
        canvas.removeEventListener('mousemove', onMouseMove, false);
        canvas.removeEventListener('touchstart', onTouchStart, false);
        canvas.removeEventListener('touchend', onTouchEnd, false);
        canvas.removeEventListener('touchcancel', onTouchEnd, false);
        canvas.removeEventListener('touchmove', onTouchMove, false);

        window.removeEventListener('resize', resizeCanvas, false);
        window.removeEventListener('load', init, false);
    }

    function onMouseDown(e) {
        rawBrushData.push({ x: e.clientX, y: e.clientY });

        drawing = true;
        dirty = true;

        ctx.beginPath();
        ctx.arc(e.clientX, e.clientY, paintSize / 2, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.beginPath();
        ctx.moveTo(e.clientX, e.clientY);
    }

    function onMouseUp(e) {
        drawing = false;
        finalizeDrawing();
    }

    function onMouseMove(e) {
        if (!drawing) return

        rawBrushData.push({ x: e.clientX, y: e.clientY });

        ctx.lineTo(e.clientX, e.clientY);
        ctx.lineWidth = paintSize;
        ctx.lineCap = 'round';
        ctx.strokeStyle = color;
        ctx.stroke();
    }

    function onDrawToolSelected(type, el, size) {
        currentTool = type;
        color = prevColor ?? color;
        paintSize = size;
        prevColor = null;

        // Select in UI
        if (selectedBtn) {
            selectedBtn.classList.remove("selected");
        }
        selectedBtn = el
        selectedBtn.classList.add("selected");
    }

    function onEraserSelected() {
        currentTool = 'eraser';
        prevColor = prevColor ?? color;
        paintSize = eraserSize;
        color = eraserColor;

        // Select in UI
        if (selectedBtn) {
            selectedBtn.classList.remove("selected");
        }
        selectedBtn = eraserBtn;
        selectedBtn.classList.add("selected");
    }

    function finalizeDrawing() {
        if (!rawBrushData) return;

        if (!drawingBoundary) drawingBoundary = { x1: window.innerWidth, y1: window.innerHeight, x2: 0, y2: 0 }

        for (point in rawBrushData) {
            drawingBoundary.x2 = Math.max(drawingBoundary.x2, rawBrushData[point].x);
            drawingBoundary.y2 = Math.max(drawingBoundary.y2, rawBrushData[point].y);
            drawingBoundary.x1 = Math.min(drawingBoundary.x1, rawBrushData[point].x);
            drawingBoundary.y1 = Math.min(drawingBoundary.y1, rawBrushData[point].y);
        }

        finalizePath = (currentTool === 'painter')

        if (finalizePath) {
            if (rawBrushData.length < 2) {
                vctx.beginPath();
                vctx.arc(rawBrushData[0].x, rawBrushData[0].y, paintSize / 2, 0, Math.PI * 2);
                vctx.fillStyle = color;
                vctx.fill();
            } else {
                vctx.beginPath();
                vctx.moveTo(rawBrushData[0].x, rawBrushData[0].y);
                for (i = 1; i < rawBrushData.length - 2; i++) {
                    let mid = {
                        x: (rawBrushData[i].x + rawBrushData[i + 1].x) / 2,
                        y: (rawBrushData[i].y + rawBrushData[i + 1].y) / 2
                    };
                    vctx.quadraticCurveTo(rawBrushData[i].x, rawBrushData[i].y, mid.x, mid.y);
                }
                vctx.quadraticCurveTo(rawBrushData[i].x, rawBrushData[i].y, rawBrushData[i + 1].x, rawBrushData[i + 1].y);

                vctx.lineWidth = paintSize;
                vctx.lineCap = 'round';
                vctx.strokeStyle = color;
                vctx.stroke();
            }
        } else {
            // Copy without finalizing
            vctx.drawImage(canvas, 0, 0)
        }
        // Update from virtual canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(vcanvas, 0, 0);

        rawBrushData = [];
    }


    function onTouchStart(e) {
        preventTouchClick(e);
        canvas.dispatchEvent(new MouseEvent('mousedown', {
            clientX: e.touches[0].clientX,
            clientY: e.touches[0].clientY
        }));
    }

    function onTouchEnd(e) {
        preventTouchClick(e);
        canvas.dispatchEvent(new MouseEvent('mouseup', {}));
    }

    function onTouchMove(e) {
        preventTouchClick(e);
        canvas.dispatchEvent(new MouseEvent('mousemove', {
            clientX: e.touches[0].clientX,
            clientY: e.touches[0].clientY
        }));
    }

    function preventTouchClick(e) {
        if (e.target === canvas) {
            e.preventDefault();
        }
    }

    function init() {
        color = document.getElementById('color').value;
        resizeCanvas();
    }

    function resizeCanvas() {
        canvas.width = window.innerWidth;
        vcanvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        vcanvas.height = window.innerHeight;
        drawingBoundary = null;
    }

    function clearCanvas() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        vctx.clearRect(0, 0, vcanvas.width, vcanvas.height);
        drawingBoundary = null;
    }

    function subscribeToGameEvents() {
        let url = new URL("/web/app/events", window.location.href);
        url.searchParams.set('_auth', initData);
        url.searchParams.set('gameId', gameId);

        let gameEventsListener = new EventSource(url);
        gameEventsListener.addEventListener('word', (event) => {
            drawingWord = event.data;
            showWord();
        });
        gameEventsListener.addEventListener('error', (event) => {
            showFullBlockingMessage(_(event.data))
            clearAll();
        });
        return gameEventsListener;
    }

    function showWord() {
        if (drawingWord) {
            Telegram.WebApp.showPopup({ title: _('word'), message: drawingWord });
            return;
        }

        let url = new URL('/web/app/word', window.location.href);
        url.searchParams.set('_auth', initData);
        url.searchParams.set('gameId', gameId);

        let XHR = new XMLHttpRequest();
        XHR.addEventListener('load', event => {
            if (event.target.status < 400) {
                drawingWord = event.target.response

                Telegram.WebApp.showPopup({ title: _('word'), message: drawingWord });
            } else {
                showFullBlockingMessage(_(event.target.response));
                clearAll();
            }
        });
        XHR.open('GET', url);
        XHR.send();
    }

    function publishImage() {
        if (drawing || !dirty || drawingBoundary == null) return;

        dirty = false;

        bounded_vcanvas = document.createElement('canvas');

        const boundWidth = drawingBoundary.x2 - drawingBoundary.x1 + publishImagePadding * 2,
            boundHeight = drawingBoundary.y2 - drawingBoundary.y1 + publishImagePadding * 2;

        bounded_vcanvas.width = boundWidth;
        bounded_vcanvas.height = boundHeight;

        bounded_vctx = bounded_vcanvas.getContext('2d');
        bounded_vctx.drawImage(
            vcanvas,
            drawingBoundary.x1 - publishImagePadding, drawingBoundary.y1 - publishImagePadding,
            boundWidth, boundHeight,
            0, 0,
            boundWidth, boundHeight
        );

        bounded_vcanvas.toBlob((blob) => {
            let formData = new FormData();
            formData.append('_auth', initData)
            formData.append('image', blob, 'image.webp')
            formData.append('gameId', gameId)

            let XHR = new XMLHttpRequest();
            XHR.open('POST', '/web/app/update');
            XHR.send(formData);

        }, 'image/webp', 0.1);
    }

    function showFullBlockingMessage(message) {
        message_el = document.getElementById('fullscreen-message');
        message_el.innerText = message;
        message_el.style.visibility = 'visible';
    }

    function clearAll() {
        detachListeners();
        clearInterval(intervalHandle);
        eventSource.close();
    }
})();