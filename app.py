from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_wtf.csrf import CSRFProtect
from datetime import datetime
import os

app = Flask(__name__)
csrf = CSRFProtect(app)  # CSRF защита
basedir = os.path.abspath(os.path.dirname(__file__))

# Конфигурация
app.config['SECRET_KEY'] = 'your-very-secret-key-here'  # Замените на реальный ключ
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'database.db')
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'images', 'products')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Создание директорий
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)

# Инициализация расширений
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите в систему'

# Модели данных
wishlist = db.Table('wishlist',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'), primary_key=True)
)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    preferences = db.Column(db.String(50), default='all')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    cart_items = db.relationship('CartItem', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    wishlist = db.relationship('Product', secondary=wishlist, lazy='dynamic',
                             backref=db.backref('wishing_users', lazy='dynamic'))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def cart_items_count(self):
        return self.cart_items.count()

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    old_price = db.Column(db.Float)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(200), default='images/products/no-image.png')
    rating = db.Column(db.Float, default=0)
    badge = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product', lazy='joined')

# Вспомогательные функции
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_variables():
    return dict(
        view_functions=app.view_functions,
        categories=db.session.query(Product.category.distinct()).all()
    )

# Middleware
@app.before_request
def before_request():
    if request.endpoint == 'static' and 'filename' not in request.view_args:
        abort(404)

# Маршруты аутентификации
@app.route('/login', methods=['GET', 'POST'])
def login():
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
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Пароли не совпадают', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Это имя пользователя уже занято', 'danger')
            return redirect(url_for('register'))
        
        if email and User.query.filter_by(email=email).first():
            flash('Этот email уже используется', 'danger')
            return redirect(url_for('register'))
        
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
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

# Основные маршруты
@app.route('/')
def index():
    category = request.args.get('category', 'all')
    
    if current_user.is_authenticated and category == 'all':
        category = current_user.preferences

    products_query = Product.query
    if category != 'all':
        products_query = products_query.filter_by(category=category)
    
    products = products_query.all()
    
    for product in products:
        if not product.image_url or not os.path.exists(os.path.join('static', product.image_url)):
            product.image_url = 'images/products/no-image.png'
    
    recommended = Product.query.order_by(Product.rating.desc()).limit(4).all()
    categories = db.session.query(Product.category.distinct()).all()
    categories = [cat[0] for cat in categories]
    
    return render_template('index.html',
                         products=products,
                         recommended_products=recommended,
                         current_category=category,
                         categories=categories)

@app.route('/catalog')
def catalog():
    products = Product.query.all()
    categories = db.session.query(Product.category.distinct()).all()
    categories = [cat[0] for cat in categories]
    
    return render_template('catalog.html',
                         products=products,
                         categories=categories)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product/detail.html', product=product)


# Админ-маршруты
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))
    
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
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        price = float(request.form.get('price'))
        old_price = float(request.form.get('old_price')) if request.form.get('old_price') else None
        category = request.form.get('category')
        rating = float(request.form.get('rating', 0))
        badge = request.form.get('badge')
        
        image_url = 'images/products/no-image.png'
        if 'image' in request.files:
            file = request.files['image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_url = f'images/products/{filename}'
        
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
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))
    
    product = Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.description = request.form.get('description')
        product.price = float(request.form.get('price'))
        product.old_price = float(request.form.get('old_price')) if request.form.get('old_price') else None
        product.category = request.form.get('category')
        product.rating = float(request.form.get('rating', 0))
        product.badge = request.form.get('badge')
        
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
    product = Product.query.get_or_404(product_id)
    in_wishlist = current_user.wishlist.filter_by(id=product_id).first()
    
    if in_wishlist:
        current_user.wishlist.remove(product)
        message = 'Товар удален из избранного'
    else:
        current_user.wishlist.append(product)
        message = 'Товар добавлен в избранное'
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': message,
        'in_wishlist': not in_wishlist
    })

# Маршруты для предпочтений
@app.route('/update_preferences', methods=['POST'])
@login_required
def update_preferences():
    category = request.form.get('category', 'all')
    current_user.preferences = category
    db.session.commit()
    return jsonify({'success': True})

# Маршрут для получения количества товаров в корзине
@app.route('/get_cart_count')
@login_required
def get_cart_count():
    return jsonify({
        'success': True,
        'count': current_user.cart_items_count
    })

# Корзина
@app.route('/cart')
@login_required
def view_cart():
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
    
    total = sum(item.product.price * item.quantity for item in valid_items)
    
    return render_template('cart/checkout.html',
                         cart_items=valid_items,
                         total_price=total)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({
            'success': False,
            'message': 'Товар не найден'
        }), 404
    
    cart_item = CartItem.query.filter_by(
        user_id=current_user.id,
        product_id=product_id
    ).first()
    
    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(
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
    action = request.form.get('action')
    cart_item = CartItem.query.filter_by(
        user_id=current_user.id,
        product_id=product_id
    ).first_or_404()
    
    if action == 'increase':
        cart_item.quantity += 1
    elif action == 'decrease':
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
        else:
            db.session.delete(cart_item)
            db.session.commit()
            flash('Товар удален из корзины', 'info')
            return redirect(url_for('view_cart'))
    
    db.session.commit()
    flash('Количество товара обновлено', 'success')
    return redirect(url_for('view_cart'))

    

@app.route('/remove_from_cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
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

@app.route('/account')
@login_required
def account():
    return render_template('account/index1.html')

# Избранные товары
@app.route('/account/wishlist')
@login_required
def account_wishlist():
    wishlist_items = current_user.wishlist.all()
    return render_template('account/wishlist.html', 
                         wishlist_items=wishlist_items)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

    app.run(debug=True)

