# Импорт необходимых модулей
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect
from datetime import datetime
import os

# Инициализация Flask приложения
app = Flask(__name__)
csrf = CSRFProtect(app)  # Включение CSRF защиты для всех форм
basedir = os.path.abspath(os.path.dirname(__file__))

# Конфигурация приложения
app.config['SECRET_KEY'] = 'your-very-secret-key-here'  # Секретный ключ для сессий и защиты форм
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'database.db')  # Путь к БД
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'images', 'products')  # Папка для загрузки изображений
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}  # Разрешенные расширения файлов
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Отключаем уведомления об изменениях

# Создание необходимых директорий, если они не существуют
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)

# Инициализация расширений
db = SQLAlchemy(app)  # ORM для работы с базой данных
login_manager = LoginManager(app)  # Менеджер аутентификации
login_manager.login_view = 'login'  # Страница входа
login_manager.login_message = 'Пожалуйста, войдите в систему'  # Сообщение при необходимости входа

# Определение таблицы связей для избранного (многие-ко-многим)
wishlist = db.Table('wishlist',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'), primary_key=True)
)

# Модель пользователя
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)  # Уникальное имя пользователя
    email = db.Column(db.String(120), unique=True, nullable=True)  # Уникальный email (необязательный)
    password_hash = db.Column(db.String(128))  # Хеш пароля
    is_admin = db.Column(db.Boolean, default=False)  # Флаг администратора
    preferences = db.Column(db.String(50), default='all')  # Предпочтения пользователя (категории)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Дата создания
    
    # Связи с другими таблицами
    cart_items = db.relationship('CartItem', backref='user', lazy='dynamic', cascade='all, delete-orphan')  # Корзина
    wishlist = db.relationship('Product', secondary=wishlist, lazy='dynamic',
                             backref=db.backref('wishing_users', lazy='dynamic'))  # Избранное

    # Методы для работы с паролями
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Свойство для подсчета товаров в корзине
    @property
    def cart_items_count(self):
        return self.cart_items.count()

# Модель товара
class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Название товара
    description = db.Column(db.Text)  # Описание товара
    price = db.Column(db.Float, nullable=False)  # Текущая цена
    old_price = db.Column(db.Float)  # Старая цена (для отображения скидки)
    category = db.Column(db.String(50), nullable=False)  # Категория товара
    image_url = db.Column(db.String(200), default='images/products/no-image.png')  # Путь к изображению
    rating = db.Column(db.Float, default=0)  # Рейтинг товара
    badge = db.Column(db.String(20))  # Бейдж (новинка, акция и т.д.)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Дата создания
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Дата обновления

# Модель элемента корзины
class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)  # Ссылка на пользователя
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'), nullable=False)  # Ссылка на товар
    quantity = db.Column(db.Integer, default=1)  # Количество товара
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Дата добавления
    
    # Связь с товаром (жадная загрузка)
    product = db.relationship('Product', lazy='joined')

# Вспомогательные функции
def allowed_file(filename):
    """Проверяет, что расширение файла разрешено для загрузки"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@login_manager.user_loader
def load_user(user_id):
    """Загружает пользователя по ID для Flask-Login"""
    return User.query.get(int(user_id))

@app.context_processor
def inject_variables():
    return dict(
        view_functions=app.view_functions,
        categories=db.session.query(Product.category.distinct()).all(),
        current_year=datetime.now().year  # Добавляем текущий год для футера
    )

# Middleware
@app.before_request
def before_request():
    """Проверка перед обработкой запроса"""
    if request.endpoint == 'static' and 'filename' not in request.view_args:
        abort(404)

# Маршруты аутентификации
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Обработка входа пользователя"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            flash('Вы успешно вошли в систему', 'success')
            return redirect(next_page or url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Обработка регистрации нового пользователя"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Валидация данных
        if password != confirm_password:
            flash('Пароли не совпадают', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Это имя пользователя уже занято', 'danger')
            return redirect(url_for('register'))
        
        if email and User.query.filter_by(email=email).first():
            flash('Этот email уже используется', 'danger')
            return redirect(url_for('register'))
        
        # Создание нового пользователя
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Регистрация прошла успешно! Теперь вы можете войти', 'success')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html')

@app.route('/logout')
@login_required
def logout():
    """Выход пользователя из системы"""
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

# Основные маршруты
@app.route('/')
def index():
    """Главная страница с товарами"""
    category = request.args.get('category', 'all')
    
    # Используем предпочтения пользователя, если он авторизован
    if current_user.is_authenticated and category == 'all':
        category = current_user.preferences

    products_query = Product.query
    if category != 'all':
        products_query = products_query.filter_by(category=category)
    
    products = products_query.all()
    
    # Проверяем существование изображений товаров
    for product in products:
        if not product.image_url or not os.path.exists(os.path.join('static', product.image_url)):
            product.image_url = 'images/products/no-image.png'
    
    # Получаем рекомендуемые товары (по рейтингу)
    recommended = Product.query.order_by(Product.rating.desc()).limit(4).all()
    categories = db.session.query(Product.category.distinct()).all()
    categories = [cat[0] for cat in categories]
    
    return render_template('index.html',
                         products=products,
                         recommended_products=recommended,
                         current_category=category,
                         categories=categories)

# Добавьте в начало файла
from datetime import datetime

# Добавьте эти маршруты в app.py
@app.route('/about')
def about():
    return render_template('info/about.html')

@app.route('/privacy')
def privacy():
    return render_template('info/privacy.html')

@app.route('/shipping')
def shipping():
    return render_template('info/shipping.html')

@app.route('/returns')
def returns():
    return render_template('info/returns.html')

@app.route('/warranty')
def warranty():
    return render_template('info/warranty.html')

@app.route('/faq')
def faq():
    return render_template('info/faq.html')

@app.route('/catalog')
def catalog():
    """Страница каталога всех товаров"""
    products = Product.query.all()
    categories = db.session.query(Product.category.distinct()).all()
    categories = [cat[0] for cat in categories]
    
    return render_template('catalog.html',
                         products=products,
                         categories=categories)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """Страница деталей товара"""
    product = Product.query.get_or_404(product_id)
    return render_template('product/detail.html', product=product)


# Админ-маршруты
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Панель администратора"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))
    
    # Получаем последние товары и пользователей
    products = Product.query.order_by(Product.created_at.desc()).limit(10).all()
    users = User.query.order_by(User.id.desc()).limit(10).all()
    orders_count = CartItem.query.distinct(CartItem.user_id).count()
    
    return render_template('admin/dashboard.html',
                         products=products,
                         users=users,
                         orders_count=orders_count)

@app.route('/admin/add_product', methods=['GET', 'POST'])
@login_required
def admin_add_product():
    """Добавление нового товара (админ)"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        # Получаем данные из формы
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        old_price = float(request.form.get('old_price')) if request.form.get('old_price') else None
        category = request.form.get('category')
        rating = float(request.form.get('rating', 0))
        badge = request.form.get('badge')
        
        # Обработка загружаемого изображения
        image_url = 'images/products/no-image.png'
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = f'images/products/{filename}'
        
        # Создаем новый товар
        new_product = Product(
            name=name,
            description=description,
            price=price,
            old_price=old_price,
            category=category,
            image_url=image_url,
            rating=rating,
            badge=badge
        )
        
        db.session.add(new_product)
        db.session.commit()
        flash('Товар успешно добавлен', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/add_product.html')  

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    """Редактирование существующего товара (админ)"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))
    
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        # Обновляем данные товара
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = float(request.form.get('price'))
        product.old_price = float(request.form.get('old_price')) if request.form.get('old_price') else None
        product.category = request.form.get('category')
        product.rating = float(request.form.get('rating', 0))
        product.badge = request.form.get('badge')
        
        # Обновляем изображение, если загружено новое
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                product.image_url = f'images/products/{filename}'
        
        db.session.commit()
        flash('Товар успешно обновлен', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/edit_product.html', product=product)

@app.route('/delete_product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    """Удаление товара (админ)"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))
    
    product = Product.query.get_or_404(product_id)
    db.session.delete(product)
    db.session.commit()
    flash('Товар успешно удален', 'success')
    return redirect(url_for('admin_dashboard'))

# Маршруты для избранного
@app.route('/toggle_wishlist/<int:product_id>', methods=['POST'])
@login_required
def toggle_wishlist(product_id):
    """Добавление/удаление товара из избранного"""
    product = Product.query.get_or_404(product_id)
    in_wishlist = current_user.wishlist.filter_by(id=product_id).first()
    
    if in_wishlist:
        current_user.wishlist.remove(product)
        message = 'Товар удален из избранного'
    else:
        current_user.wishlist.append(product)
        message = 'Товар добавлен в избранное'
    
    db.session.commit()
    
    # Возвращаем JSON ответ для AJAX запросов
    return jsonify({
        'success': True,
        'message': message,
        'in_wishlist': not in_wishlist
    })

# Маршруты для предпочтений
@app.route('/update_preferences', methods=['POST'])
@login_required
def update_preferences():
    """Обновление предпочтений пользователя (любимые категории)"""
    category = request.form.get('category', 'all')
    current_user.preferences = category
    db.session.commit()
    return jsonify({'success': True})

# Маршрут для получения количества товаров в корзине
@app.route('/get_cart_count')
@login_required
def get_cart_count():
    """Возвращает количество товаров в корзине (для AJAX)"""
    return jsonify({
        'success': True,
        'count': current_user.cart_items_count
    })

# Корзина
@app.route('/cart')
@login_required
def view_cart():
    """Просмотр корзины пользователя"""
    cart_items = CartItem.query.filter_by(
        user_id=current_user.id
    ).options(db.joinedload(CartItem.product)).all()
    
    # Фильтруем и удаляем несуществующие товары
    valid_items = []
    for item in cart_items:
        if item.product is None:
            db.session.delete(item)
        else:
            valid_items.append(item)
    
    if len(cart_items) != len(valid_items):
        db.session.commit()
        flash('Некоторые товары были удалены из корзины, так как больше не доступны', 'info')
    
    # Считаем общую стоимость
    total = sum(item.product.price * item.quantity for item in valid_items)
    
    return render_template('cart/checkout.html',
                         cart_items=valid_items,
                         total_price=total)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    """Добавление товара в корзину"""
    product = Product.query.get(product_id)
    if not product:
        return jsonify({
            'success': False,
            'message': 'Товар не найден'
        }), 404
    
    # Проверяем, есть ли уже такой товар в корзине
    cart_item = CartItem.query.filter_by(
        user_id=current_user.id,
        product_id=product_id
    ).first()
    
    if cart_item:
        cart_item.quantity += 1  # Увеличиваем количество, если товар уже в корзине
    else:
        cart_item = CartItem(  # Создаем новый элемент корзины
            user_id=current_user.id,
            product_id=product_id
        )
        db.session.add(cart_item)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Товар добавлен в корзину',
        'cart_count': current_user.cart_items_count
    })

@app.route('/update_cart/<int:product_id>', methods=['POST'])
@login_required
def update_cart(product_id):
    """Изменение количества товара в корзине"""
    action = request.form.get('action')
    cart_item = CartItem.query.filter_by(
        user_id=current_user.id,
        product_id=product_id
    ).first_or_404()
    
    if action == 'increase':
        cart_item.quantity += 1  # Увеличиваем количество
    elif action == 'decrease':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1  # Уменьшаем количество
        else:
            db.session.delete(cart_item)  # Удаляем, если количество = 1
            db.session.commit()
            flash('Товар удален из корзины', 'info')
            return redirect(url_for('view_cart'))
    
    db.session.commit()
    flash('Количество товара обновлено', 'success')
    return redirect(url_for('view_cart'))

@app.route('/remove_from_cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    """Удаление товара из корзины"""
    item = CartItem.query.filter_by(
        id=item_id,
        user_id=current_user.id
    ).first_or_404()
    
    db.session.delete(item)
    db.session.commit()
    
    flash('Товар удален из корзины', 'info')
    return redirect(url_for('view_cart'))

# Маршрут для оформления заказа
@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Оформление заказа"""
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    
    if not cart_items:
        flash('Ваша корзина пуста', 'warning')
        return redirect(url_for('view_cart'))
    
    if request.method == 'POST':
        # Здесь должна быть логика обработки заказа
        # Очищаем корзину после оформления заказа
        CartItem.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        flash('Заказ успешно оформлен!', 'success')
        return redirect(url_for('index'))
    
    total = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('cart/checkout.html', cart_items=cart_items, total_price=total)

# Личный кабинет
@app.route('/account')
@login_required
def account():
    """Страница личного кабинета"""
    return render_template('account/index1.html')

# Избранные товары
@app.route('/account/wishlist')
@login_required
def account_wishlist():
    """Страница избранных товаров пользователя"""
    wishlist_items = current_user.wishlist.all()
    return render_template('account/wishlist.html', 
                         wishlist_items=wishlist_items)

# Точка входа в приложение
if __name__ == '__main__':
    # Создаем таблицы в базе данных, если их нет
    with app.app_context():
        db.create_all()
        
        # Создаем администратора по умолчанию, если его нет
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

    # Запускаем приложение
    app.run(debug=True)
    