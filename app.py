from flask import Flask, render_template, request, redirect, url_for, flash, session 
import mysql.connector
from datetime import datetime
import mysql.connector.pooling

app = Flask (__name__)

'''
db_config = { 
    'host': 'database-1.c0umnpuldfel.us-east-1.rds.amazonaws.com',
    'user': 'admin',
    'password': 'admin123',
    'database': 'database-1'
}
'''
db_config = { 
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'aws_mini'
}

try:
    conn = mysql.connector.connect(**db_config)
    if conn.is_connected():
        print("Successfully connected to the database!")
        conn.close()
except mysql.connector.Error as err:
    print(f"Error: {err}")

cnxpool = mysql.connector.pooling. MySQLConnectionPool(pool_name="mypool",
                                                       pool_size=5, 
                                                       **db_config)

def get_db_connection():
    try:
        return cnxpool.get_connection()
    except mysql.connector.Error as err:
        print(f"Error: {err}")
        return None
    
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        password = request.form.get('password')
        address = request.form.get('address')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (name, mobile, email, password, address) VALUES (%s, %s, %s, %s, %s)', 
            (name, mobile, email, password, address))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password= request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name'] 
            if (user['id'] == 1):
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('shop'))
        else:
            flash('Invalid email or password!')

    return render_template('login.html')

@app.route('/shop')
def shop():
    return render_template('shop.html')
    
@app.route('/items', methods=['GET', 'POST'])
def items():
    if request.method == 'POST':
        item_name = request.form.get('name')
        item_price = float(request.form.get('price')) 
        item_quantity = int(request.form.get('quantity'))

        cart_items = session.get('cart_items', [])

        for item in cart_items:
            if item['name']==item_name:
                item['quantity'] += item_quantity
                break
        else:
            cart_items.append({'name': item_name, 'price': item_price, 'quantity': item_quantity})
        
        session['cart_items'] = cart_items
        flash(f'{item_name} added to your cart!')
        return redirect(url_for('items'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT item_id, item_name, price FROM items')
    items = cursor.fetchall()
    cursor.close()
    conn.close()

    cart_items = session.get('cart_items', [])
    return render_template('items.html', items=items, cart_items=cart_items)


@app.route('/cart', methods=['GET', 'POST'])
def cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT address FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    
    cart_items = session.get('cart_items', [])
    total_amount = sum(item['price'] * item['quantity'] for item in cart_items)

    return render_template('cart.html', cart_items=cart_items, total_amount=total_amount, user_address=user['address'])
    

@app.route('/user_dashboard', methods=['GET','POST'])
def user_dashboard(): 
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        delivery_address = request.form.get("delivery_address")
        payment_method = request.form.get("payment_method")
        items = session.get('cart_items', [])
        total_price = 0
        for item in items:
            total_price += item['price'] * item['quantity']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO orders (user_id, delivery_address, payment_method, status, order_date, total_price) ' 
            'VALUES (%s, %s, %s, %s, %s, %s)',
            (session['user_id'], delivery_address, payment_method, 'Yet to Ship', datetime.now(), total_price)
        )
        order_id = cursor.lastrowid
        for item in items:
            cursor.execute(
                'INSERT INTO order_items (order_id, item_name, item_price, item_quantity) '
                'VALUES (%s, %s, %s, %s)',
                (order_id, item['name'], item['price'], item['quantity'])
            )
        conn.commit() 
        cursor.close()
        conn.close()
        session['cart_items'] = []
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT o.id, o.total_price, o.status, o.order_date,
            GROUP_CONCAT(CONCAT(oi.item_name, ' (x', oi.item_quantity, ')')) AS myitems
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE o.user_id = %s
        GROUP BY o.id
    ''', (session['user_id'],))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('user_dashboard.html', orders=orders)

@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if request.method == 'POST':
        order_id = request.form['order_id']
        status = request.form['status']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE orders SET status = %s WHERE id = %s', (status, order_id))
        conn.commit() 
        cursor.close()
        conn.close()

        flash('Order status updated successfully!', 'success')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute('''
        SELECT o.id, o.total_price, o.status, o.order_date, u.name AS user_name, 
                GROUP_CONCAT(CONCAT(oi.item_name, ' (x', oi.item_quantity, ')') SEPARATOR ', ') AS myitems
        FROM orders o
        JOIN users u ON o.user_id = u.id
        JOIN order_items oi ON o.id = oi.order_id 
        GROUP BY o.id
    ''')
    
    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('admin_dashboard.html', orders=orders)

@app.route('/logout')
def logout():
     session.clear()
     return render_template('home.html')


if __name__ == '_main_':
    app.run(debug=True)