import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime

from sqlalchemy import Null
from werkzeug.utils import secure_filename
import uuid
from base64 import b64encode

from sqlalchemy.orm import relationship


app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'static/uploads'

app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'static', 'uploads' )

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# функция для проверки разрешения
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

class Client(db.Model):
    __tablename__ = 'clients'
    client_id = db.Column(db.Integer, primary_key=True )
    client_name = db.Column(db.Text, nullable=False)
    phone = db.Column(db.Text, nullable=False)
    tg_nik = db.Column(db.Text, nullable=False)
    client_password = db.Column(db.Text, nullable=False)
    create_dttm = db.Column(db.DateTime, default=datetime.utcnow )

class GroupDebt(db.Model):
    __tablename__ = 'group_debts'
    gr_debt_id = db.Column(db.Integer, primary_key=True)
    gr_debt_amount = db.Column(db.Integer, nullable=False)
    create_dttm = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    borrower_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'), nullable=False) #  это debter_id

class Debt(db.Model):
    __tablename__ = 'debts'
    debt_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    debt_amount = db.Column(db.Integer, nullable=False)
    create_dttm = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    close_dttm = db.Column(db.DateTime, default=lambda :datetime(5999,1,1,0,0,0))              # DEFAULT '5999-01-01'
    debt_amount_return = db.Column(db.Integer, default=0)
    debt_comm = db.Column(db.Text)
    addings_flg = db.Column(db.Boolean, default=False )
    debt_group_id = db.Column(db.Integer, db.ForeignKey('group_debts.gr_debt_id'), default=-1)
    borrower_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'), nullable=False)
    debter_id = db.Column(db.Integer, db.ForeignKey('clients.client_id'), nullable=False)

    addings = db.relationship('Adding', backref='debt', lazy='joined')  # Связь для доступа к прикреплениям
    notifications = db.relationship('Notification', backref='debt', lazy='joined' )  # Связь для доступа к прикреплениям

    borrower = relationship('Client', foreign_keys=[borrower_id])
    debter = relationship('Client', foreign_keys=[debter_id])

class Adding(db.Model):
    tablename = 'addings'
    adding_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    debt_id = db.Column(db.Integer, db.ForeignKey('debts.debt_id'), nullable=False)
    adding = db.Column(db.Text, nullable=False)

class Notification(db.Model):
    tablename = 'notifications'
    notification_id = db.Column(db.Integer, primary_key=True, autoincrement=True )
    debt_id = db.Column(db.Integer, db.ForeignKey('debts.debt_id'), nullable=False)
    notification_text = db.Column(db.Text )
    send_dttm = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    read_dttm = db.Column(db.DateTime, default=lambda :datetime(5999,1,1,0,0,0))

class Transaction(db.Model):
    tablename = 'transactions'
    transaction_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    debt_id = db.Column(db.Integer, db.ForeignKey('debts.debt_id') )
    return_amount = db.Column(db.Integer, default=0)
    return_dttm = db.Column(db.DateTime, nullable=False)

class Agrements(db.Model):
    tablename = 'agrements'
    agreement_id = db.Column(db.Integer, primary_key=True)  # SERIAL PRIMARY KEY
    debt_id = db.Column(db.Integer, db.ForeignKey("debts.debt_id"), nullable=False)  # REFERENCES debts
    debter_agree = db.Column(db.Boolean)  # BOOLEAN для согласия должника
    borrower_agree = db.Column(db.Boolean)  # BOOLEAN для согласия заёмщика
    debt_amount = db.Column(db.Integer, nullable=False)
    agree_type = db.Column(db.Text, nullable=False, default='')  # TEXT NOT NULL
    transaction_id = db.Column(db.Integer, db.ForeignKey("transactions.transaction_id"))  # REFERENCES transactions


@app.route('/' )
def home():
    if "username" in session:
        user = Client.query.filter_by(client_name=session['username']).first()
        debts_give = Debt.query.filter(Debt.debter_id == user.client_id).all()
        debts_get = Debt.query.filter(Debt.borrower_id == user.client_id).all()
        return render_template('home.html', user=user, debts_give=debts_give, debts_get=debts_get)
    return render_template('start.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username' )
        password = request.form.get('password')
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        phone = request.form.get('phone')
        tg_nik = request.form.get('tg_nik')

        user_check = Client.query.filter_by(client_name=username).first()
        if user_check:
            flash('Это имя пользователя уже занято. Попробуйте другое.', 'error')
            return redirect(url_for('register'))
        user_check2 = Client.query.filter_by(client_name=phone).first()
        if user_check2:
            flash('Этот телефон уже зарегистрирован. Попробуйте другой.', 'error')
            return redirect(url_for('register'))
        user_check3 = Client.query.filter_by(client_name=tg_nik).first()
        if user_check3:
            flash('Этот тг-ник уже занят. Попробуйте другой.', 'error' )
            return redirect(url_for('register'))


        new_user = Client(client_name=username, client_password=hashed_password, phone=phone, tg_nik=tg_nik)
        db.session.add(new_user)
        db.session.commit()
        flash('Вы успешно зарегистрировались! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html' )



@app.route('/login', methods=['GET', 'POST'] )
def login():
    if request.method == 'POST':
        username = request.form.get('username' )
        password = request.form.get('password')


        user = Client.query.filter_by(client_name=username).first()
        if user and bcrypt.check_password_hash(user.client_password, password):
            session['username'] = user.client_name
            flash('Вы успешно вошли в систему!', 'success' )
            return redirect(url_for('home'))

        flash('Неверное имя пользователя или пароль.', 'error')
        return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/create_debt_give', methods=['GET', 'POST'] )
def create_debt_give():
    if request.method == 'POST':

        debt_amount = request.form['debt_amount']
        debt_comm = request.form.get('debt_comm', '')
        borrower_id = request.form['borrower_id']
        user = Client.query.filter_by(client_name=session['username']).first()


        new_debt = Debt(
            debt_amount=int(debt_amount),
            debt_comm=debt_comm,
            borrower_id=int(borrower_id),
            debter_id=user.client_id
        )
        db.session.add(new_debt)
        db.session.commit()
        if 'adding' not in request.files:
            print("Файл не был передан.")
        else:
            file = request.files['adding']
            if file.filename == '':
                print("Файл не выбран.")
            elif file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_ext = os.path.splitext(filename)[1]  # Получаем расширение файла
                unique_filename = f"{uuid.uuid4().hex}{file_ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                relative_path = f"uploads/{unique_filename}"  # Относительный путь

                # Создаём папку, если она не существует
                if not os.path.exists(app.config['UPLOAD_FOLDER']):
                    os.makedirs(app.config['UPLOAD_FOLDER'])

                try:
                    file.save(file_path)
                    print(f"Файл успешно сохранён: {file_path}")

                    # Сохраняем привязку к базе
                    new_adding = Adding(
                        debt_id=new_debt.debt_id,
                        adding=relative_path  # путь к файлу
                    )
                    db.session.add(new_adding)
                    new_debt.addings_flg = True
                    db.session.commit()

                except Exception as e:
                    print(f"Ошибка при сохранении файла: {e}")
            else:
                print("Недопустимый формат файла.")

        return redirect(url_for('home'))


        return redirect(url_for('home'))


    all_clients = Client.query.all()
    return render_template('create_debt_give.html', all_clients=all_clients)


@app.route('/create_debt_get', methods=['GET', 'POST'] )
def create_debt_get():
    user = Client.query.filter_by(client_name=session['username']).first()
    if request.method == 'POST':

        debt_amount = request.form['debt_amount']
        debt_comm = request.form.get('debt_comm', '')
        debter_id = request.form['debter_id']


        new_debt = Debt(
            debt_amount=int(debt_amount),
            debt_comm=debt_comm,
            debter_id=int(debter_id),
            borrower_id=user.client_id
        )

        db.session.add(new_debt)
        db.session.commit()

        # Обрабатываем загружаемое изображение
        if 'adding' not in request.files:
            print("Файл не был передан.")
        else:
            file = request.files['adding']
            if file.filename == '':
                print("Файл не выбран.")
            elif file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_ext = os.path.splitext(filename)[1]  # Получаем расширение файла
                unique_filename = f"{uuid.uuid4().hex}{file_ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                relative_path = f"uploads/{unique_filename}"  # Относительный путь

                # Создаём папку, если она не существует
                if not os.path.exists(app.config['UPLOAD_FOLDER']):
                    os.makedirs(app.config['UPLOAD_FOLDER'])

                try:
                    file.save(file_path)
                    print(f"Файл успешно сохранён: {file_path}")

                    # Сохраняем привязку к базе
                    new_adding = Adding(
                        debt_id=new_debt.debt_id,
                        adding=relative_path  # путь к файлу
                    )
                    db.session.add(new_adding)
                    new_debt.addings_flg = True
                    db.session.commit()

                except Exception as e:
                    print(f"Ошибка при сохранении файла: {e}")
            else:
                print("Недопустимый формат файла.")

        return redirect(url_for('home'))

    all_clients = Client.query.filter(Client.client_id != user.client_id).all()
    return render_template('create_debt_get.html', all_clients=all_clients)


@app.route('/notifications', methods=['GET', 'POST'])
def notifications():
    user = Client.query.filter_by(client_name=session['username']).first()
    debts = Debt.query.filter(Debt.debter_id == user.client_id).all()
    if request.method == 'POST':
        # Получаем данные из формы отправки новой нотификации
        debt_id = request.form.get('debt_id' )
        notification_text = request.form.get('notification_text', '')

        # Создаём новую нотификацию
        new_notification = Notification(
            debt_id=int(debt_id),
            notification_text=notification_text
        )

        db.session.add(new_notification)
        db.session.commit()

        return redirect(url_for('notifications'))

        # GET-запрос: отображаем список нотификаций
    debt_ids = [debt.debt_id for debt in Debt.query.filter(Debt.debter_id == user.client_id).all()]
    notifications = Notification.query.filter(Notification.debt_id.in_(debt_ids)).order_by(
        Notification.send_dttm.desc()).all()

    return render_template('notifications.html', notifications=notifications, user=user, debts=debts)

@app.route('/notifications_read' )
def notifications_read():
    if "username" in session:
        user = Client.query.filter_by(client_name=session['username'] ).first()
        debt_ids = [debt.debt_id for debt in Notification.query.all()]
        debts_get = Debt.query.filter((Debt.borrower_id == user.client_id) & (Debt.debt_id.in_(debt_ids)) ).all()
        return render_template('notifications_read.html', user=user, debts_get=debts_get )
    return render_template('start.html')

@app.route('/close_debt', methods=['GET', 'POST'] )
def close_debt():

    user = Client.query.filter_by(client_name=session['username']).first()
    debts = Debt.query.filter(Debt.borrower_id == user.client_id).all()

    if request.method == 'POST':
        client_id = user.client_id  # ID текущего клиента


        debt_id = request.form.get('debt_id')
        payment_amount = int(request.form.get('payment_amount', 0))


        debt = Debt.query.filter_by(debt_id=debt_id, borrower_id=client_id).first()
        if not debt:
            flash("Выбранный долг не найден!", "error")
            return redirect(url_for('close_debt'))


        remaining_amount = debt.debt_amount - debt.debt_amount_return


        if payment_amount > remaining_amount:
            flash(f"Вы не можете внести сумму больше оставшегося долга ({remaining_amount}).", "error")
            return redirect(url_for('close_debt'))


        debt.debt_amount_return += payment_amount


        if debt.debt_amount_return == debt.debt_amount:
            debt.close_dttm = datetime.utcnow()


        db.session.commit()
        #flash("Оплата внесена успешно!", "success")
        return redirect(url_for('home'))


    return render_template('close_debt.html', debts=debts)


@app.route('/create_group_debt', methods=['GET', 'POST'])
def create_group_debt():
    user = Client.query.filter_by(client_name=session['username'] ).first()
    if request.method == 'POST':
        # Получаем данные из формы
        debt_comm = request.form.get('debt_comm', '')
        borrowers = request.form.getlist('borrowers[]')  # Список должников (формат: ID1,ID2,ID3...)
        amounts = request.form.getlist('amounts[]')  # Суммы долгов для каждого должника
        print(borrowers)
        print(debt_comm)
        print(amounts)
        debter_id = user.client_id

        print(request.form)  # Полный запрос в сыром виде



        # Конвертируем суммы в числа и проверяем
        try:
            amounts = [int(amount) for amount in amounts]
        except ValueError:
            print("Ошибка: некорректный формат суммы")
            return redirect(url_for('create_group_debt'))


        debt_amount = int(sum(amounts) )

        # Создаем запись о групповом долге
        new_group_debt = GroupDebt(
            borrower_id =int(debter_id),
            gr_debt_amount =debt_amount,
        )
        db.session.add(new_group_debt)
        db.session.flush()  # Фиксируем данные временно, чтобы получить ID группового долга

        # Создаем записи о долгах для каждого должника
        for borrower_id, amount in zip(borrowers, amounts):
            new_debt = Debt(
                debt_amount=int(amount),
                debter_id =int(debter_id),  # ID должника
                debt_comm=debt_comm,  # Добавляем комментарий
                borrower_id= int(borrower_id),  # ID должника
                debt_group_id =int(new_group_debt.gr_debt_id)  # Указываем внешний ключ на групповой долг
            )
            print("lol")
            print(amount)
            db.session.add(new_debt)
            # Проверяем наличие файла и обрабатываем его, если он есть
        if 'adding' not in request.files:
            print("Файл не был передан.")
        else:
            file = request.files['adding']
            if file.filename == '':
                print("Файл не выбран.")
            elif file and allowed_file(file.filename):
                # Если файл допустимого формата, сохраняем его
                filename = secure_filename(file.filename)
                file_ext = os.path.splitext(filename)[1]  # Получаем расширение файла
                unique_filename = f"{uuid.uuid4().hex}{file_ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                relative_path = f"uploads/{unique_filename}"  # Относительный путь

                # Создаём путь к папке, если она не существует
                if not os.path.exists(app.config['UPLOAD_FOLDER']):
                    os.makedirs(app.config['UPLOAD_FOLDER'])

                try:
                    file.save(file_path)  # Сохраняем файл
                    print(f"Файл успешно сохранён: {file_path}")

                    # Создаем привязку файла к групповой записи долга
                    new_adding = Adding(
                        group_debt_id=new_group_debt.id,  # Связываем файл с группой долгов
                        adding=relative_path  # Указываем путь к файлу
                    )
                    db.session.add(new_adding)
                    new_group_debt.addings_flg = True  # Указываем, что есть привязанные файлы
                except Exception as e:
                    print(f"Ошибка при сохранении файла: {e}")
            else:
                print("Недопустимый формат файла.")

                # Финальное сохранение изменений
        db.session.commit()
        return redirect(url_for('home'))  # Redirect на главную страницу после успешного добавления
                # Загрузка данных для формы (GET-запрос)
    all_clients = Client.query.all()
    return render_template('create_group_debt.html', all_clients=all_clients)

# Выход из учетной записи
@app.route('/logout')
def logout():
    session.pop('username', None)
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('home'))


@app.route('/users', methods=['GET'])
def list_users():
    if 'username' not in session or session['username'] != 'admin':
        flash('Только администратор может видеть список пользователей!', 'error')
        return redirect(url_for('home'))

    users = Client.query.all()
    return render_template('users.html', users=users )

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)