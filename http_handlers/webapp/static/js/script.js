(function () {
    const i18n = {
        "en": {
            "close": "Close",
            "word": "Word",
            "not_host": "You`re not the host",
            "ended": "Game ended",
            "not_auth": "No authorization",
            "error": "Error"
        },
        "ru": {
            "close": "Закрыть",
            "word": "Слово",
            "not_host": "Вы не ведущий",
            "ended": "Игра закончилась",
            "not_auth": "Нет авторизации",
            "error": "Ошибка"
        },
    };

    const default_locale = "en";
    current_locale = window.navigator.language.split("-")[0];
    if (current_locale in i18n === false) current_locale = default_locale;

    _ = (key) => { return i18n[current_locale][key] ?? key; };

    Telegram.WebApp.ready();
    Telegram.WebApp.expand();
    Telegram.WebApp.enableClosingConfirmation();
    Telegram.WebApp.MainButton
        .setText(_('close'))
        .show()
        .onClick(function () {
            Telegram.WebApp.close();
        });

    const initData = Telegram.WebApp.initData;
    const initDataUnsafe = Telegram.WebApp.initDataUnsafe;

    if (!initData || !initDataUnsafe || !initDataUnsafe.start_param) {
        document.getElementById('error').style.visibility = 'visible';
        return;
    }

    // gameId__123d234f
    const gameId = initDataUnsafe.start_param;

    const canvas = document.getElementById('paintarea'),
        vcanvas = document.createElement('canvas'),
        ctx = canvas.getContext('2d'),
        vctx = vcanvas.getContext('2d'),
        bounding_pad = 18;

    let rawBrushData = [],
        drawing = false,
        dirty = false,
        paintSize = 3,
        color = '#000000',
        prevColor = null,
        eraserSize = 12,
        eraserColor = '#ffffff',
        currentTool = 'painter',
        drawingBoundary = null;

    attachCanvasListeners();

    showWord();
    subscribeToGameEvents();
    setInterval(() => publishImage(), 1_500);

    function attachCanvasListeners() {
        document.addEventListener('touchmove', (e) => { e.preventDefault() }, { passive: false });

        // Drawing buttons
        document.getElementById('small-dot').onclick = () => {
            currentTool = 'painter';
            color = prevColor ?? color;
            paintSize = 3;
            prevColor = null
        };
        document.getElementById('medium-dot').onclick = () => {
            currentTool = 'painter';
            color = prevColor ?? color;
            paintSize = 6;
            prevColor = null
        };
        document.getElementById('large-dot').onclick = () => {
            currentTool = 'painter';
            color = prevColor ?? color;
            paintSize = 12;
            prevColor = null
        };
        document.getElementById('eraser').onclick = () => {
            currentTool = 'eraser';
            prevColor = prevColor ?? color;
            paintSize = eraserSize;
            color = eraserColor
        }
        document.getElementById('clear').onclick = clearCanvas;
        document.getElementById('color').onchange = (e) => { color = e.target.value };

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
        document.getElementById('small-dot').onclick = null;
        document.getElementById('medium-dot').onclick = null;
        document.getElementById('large-dot').onclick = null;
        document.getElementById('clear').onclick = null;
        document.getElementById('eraser').onclick = null;
        document.getElementById('color').onchange = null;

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

        let eventSource = new EventSource(url);
        eventSource.onmessage = function(event) {
            error_el = document.getElementById('error');
            error_el.innerText = _(event.data);
            error_el.style.visibility = 'visible';
            eventSource.close();
            detachListeners();
        };
    }

    function showWord() {
        let url = new URL('/web/app/word', window.location.href);
        url.searchParams.set('_auth', initData);
        url.searchParams.set('gameId', gameId);

        let XHR = new XMLHttpRequest();
        XHR.addEventListener('load', event => {
            if (event.target.status < 400) {
                console.log("Success Status: " + event.target.status);
                Telegram.WebApp.showPopup({ title: _('word'), message: event.target.response });
            } else {
                error_el = document.getElementById('error');
                error_el.innerText = _(event.target.response);
                error_el.style.visibility = 'visible';

                detachListeners();

                console.error("Error Status: " + event.target.status);
            }
        });
        XHR.addEventListener('error', event => {
            error_el = document.getElementById('error');
            error_el.innerText = _('error');
            error_el.style.visibility = 'visible';
            
            console.error("Error Status: " + event.target.status);
        });
        XHR.open('GET', url);
        XHR.send();
    }

    function publishImage() {
        if (drawing || !dirty || drawingBoundary == null) return;

        dirty = false;

        bounded_vcanvas = document.createElement('canvas');

        const boundWidth = drawingBoundary.x2 - drawingBoundary.x1 + bounding_pad * 2,
            boundHeight = drawingBoundary.y2 - drawingBoundary.y1 + bounding_pad * 2;

        bounded_vcanvas.width = boundWidth;
        bounded_vcanvas.height = boundHeight;

        bounded_vctx = bounded_vcanvas.getContext('2d');
        bounded_vctx.drawImage(
            vcanvas,
            drawingBoundary.x1 - bounding_pad, drawingBoundary.y1 - bounding_pad,
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
            XHR.addEventListener('load', event => {
                if (event.target.status === 200) {
                    console.log("Success Status: " + event.target.status);
                } else {
                    console.error("Error Status: " + event.target.status);
                }
            });
            XHR.addEventListener('error', event => {
                console.error("Error Status: " + event.target.status);
            });
            XHR.open('POST', '/web/app/update');
            XHR.send(formData);

        }, 'image/webp', 0.1);
    }
})();