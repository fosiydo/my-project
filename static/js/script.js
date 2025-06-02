document.addEventListener('DOMContentLoaded', function() {
    // Добавление в корзину
    document.querySelectorAll('.add-to-cart').forEach(button => {
        button.addEventListener('click', function() {
            const productId = this.getAttribute('data-product-id');
            
            fetch(`/add_to_cart/${productId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    updateCartCount(data.cart_count);
                    showFlashMessage(data.message, 'success');
                } else {
                    showFlashMessage(data.message, 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showFlashMessage('Произошла ошибка при добавлении в корзину', 'error');
            });
        });
    });

    // Избранное
    document.querySelectorAll('.wishlist').forEach(button => {
        button.addEventListener('click', function() {
            if (!document.body.classList.contains('logged-in')) {
                showFlashMessage('Для добавления в избранное войдите в систему', 'warning');
                return;
            }

            const productId = this.getAttribute('data-product-id');
            fetch(`/toggle_wishlist/${productId}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.classList.toggle('active');
                    const svg = this.querySelector('svg');
                    svg.setAttribute('fill', data.in_wishlist ? 'currentColor' : 'none');
                    showFlashMessage(data.message, 'success');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showFlashMessage('Произошла ошибка', 'error');
            });
        });
    });

    // Фильтрация по категориям
    document.querySelectorAll('.preference-btn').forEach(button => {
        button.addEventListener('click', function() {
            const category = this.getAttribute('data-category');
            document.querySelectorAll('.preference-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            this.classList.add('active');
            
            if (document.body.classList.contains('logged-in')) {
                fetch('/update_preferences', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'X-CSRFToken': getCSRFToken(),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: `category=${encodeURIComponent(category)}`
                });
            }
        });
    });

    // Инициализация корзины
    if (document.body.classList.contains('logged-in')) {
        updateCartCount();
    }
});

function updateCartCount(count = null) {
    if (count !== null) {
        const cartCountElements = document.querySelectorAll('.cart-count');
        cartCountElements.forEach(el => el.textContent = count);
        return;
    }

    fetch('/get_cart_count', {
        headers: {
            'X-CSRFToken': getCSRFToken()
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const cartCountElements = document.querySelectorAll('.cart-count');
            cartCountElements.forEach(el => el.textContent = data.count);
        }
    })
    .catch(error => console.error('Error:', error));
}

function showFlashMessage(message, type) {
    const flashContainer = document.querySelector('.flash-messages') || createFlashContainer();
    const flash = document.createElement('div');
    flash.className = `flash flash-${type}`;
    flash.textContent = message;
    flashContainer.appendChild(flash);
    
    setTimeout(() => flash.remove(), 5000);
}

function createFlashContainer() {
    const container = document.createElement('div');
    container.className = 'flash-messages';
    document.body.appendChild(container);
    return container;
}

function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]').content;
}

const categoryButtons = document.querySelectorAll('.preference-btn');
    
// Обработчик клика для кнопок категорий
categoryButtons.forEach(button => {
    button.addEventListener('click', function() {
        const category = this.dataset.category;
        
        // Удаляем класс active у всех кнопок
        categoryButtons.forEach(btn => btn.classList.remove('active'));
        
        // Добавляем класс active текущей кнопке
        this.classList.add('active');
        
        // Если выбрана категория "all", показываем все товары
        if (category === 'all') {
            document.querySelectorAll('.product-card').forEach(card => {
                card.style.display = 'block';
            });
            return;
        }
        
        // Фильтруем товары по выбранной категории
        document.querySelectorAll('.product-card').forEach(card => {
            const cardCategory = card.querySelector('.product-category').textContent.toLowerCase();
            if (cardCategory === category) {
                card.style.display = 'block';
            } else {
                card.style.display = 'none';
            }
        });
    });
});

// Если есть параметр category в URL, активируем соответствующую кнопку
const urlParams = new URLSearchParams(window.location.search);
const categoryParam = urlParams.get('category');
if (categoryParam) {
    const activeButton = document.querySelector(`.preference-btn[data-category="${categoryParam}"]`);
    if (activeButton) {
        activeButton.click();
    }
}
