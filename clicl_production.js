/**
 * Счётчик кликов для отправки данных на сервер мониторинга.
 * Вставьте этот код на все страницы сайта.
 */
(function() {
    const API_URL = 'https://click-production.up.railway.app';  // URL вашего Flask-сервера

    // Отслеживание просмотра страницы
    function trackPageview() {
        fetch(API_URL + '/api/track/pageview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                page: window.location.pathname
            })
        }).catch(() => {});
    }

    // Отслеживание кликов по элементам
    function trackClick(element, selector) {
        fetch(API_URL + '/api/track/click', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                page: window.location.pathname,
                element: selector || element.tagName,
                referrer: document.referrer
            })
        }).catch(() => {});
    }

    // Слушатель кликов
    document.addEventListener('click', function(e) {
        const target = e.target.closest('a, button, [data-track]');
        if (target) {
            const selector = target.getAttribute('data-track') 
                || target.id 
                || target.className 
                || target.tagName;
            trackClick(target, selector);
        }
    });

    // Отслеживание просмотра при загрузке
    if (document.readyState === 'complete') {
        trackPageview();
    } else {
        window.addEventListener('load', trackPageview);
    }
})();
