import os
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from flask_bcrypt import Bcrypt
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Length

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///students.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message_category = "warning"

    with app.app_context():
        db.create_all()

    register_routes(app)
    return app


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password: str):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def check_password(self, password: str) -> bool:
        return bcrypt.check_password_hash(self.password_hash, password)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    roll_no = db.Column(db.String(50), unique=True, nullable=False)
    grade = db.Column(db.String(10), nullable=False)


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class RegisterForm(FlaskForm):
    name = StringField("Full Name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=6, message="Password should be at least 6 characters"),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password")]
    )
    submit = SubmitField("Create Account")


class StudentForm(FlaskForm):
    student_id = StringField("Student ID", validators=[DataRequired(), Length(max=50)])
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    roll_no = StringField("Roll No.", validators=[DataRequired(), Length(max=50)])
    grade = StringField("Grade", validators=[DataRequired(), Length(max=10)])
    submit = SubmitField("Save Student")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def register_routes(app: Flask):
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data.lower()).first()
            if user and user.check_password(form.password.data):
                login_user(user)
                flash("Welcome back!", "success")
                return redirect(url_for("dashboard"))
            flash("Invalid credentials. Please try again.", "danger")
        return render_template("login.html", form=form)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        form = RegisterForm()
        if form.validate_on_submit():
            if User.query.filter_by(email=form.email.data.lower()).first():
                flash("Email already registered.", "warning")
            else:
                user = User(
                    name=form.name.data,
                    email=form.email.data.lower(),
                )
                user.set_password(form.password.data)
                db.session.add(user)
                db.session.commit()
                flash("Account created. Please log in.", "success")
                return redirect(url_for("login"))
        return render_template("register.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        students = Student.query.order_by(Student.name).all()
        return render_template("dashboard.html", students=students)

    @app.route("/students/new", methods=["GET", "POST"])
    @login_required
    def add_student():
        form = StudentForm()
        if form.validate_on_submit():
            if Student.query.filter_by(student_id=form.student_id.data).first():
                flash("Student ID already exists.", "warning")
                return render_template("student_form.html", form=form, is_edit=False)
            if Student.query.filter_by(roll_no=form.roll_no.data).first():
                flash("Roll number already exists.", "warning")
                return render_template("student_form.html", form=form, is_edit=False)
            student = Student(
                student_id=form.student_id.data,
                name=form.name.data,
                roll_no=form.roll_no.data,
                grade=form.grade.data,
            )
            db.session.add(student)
            db.session.commit()
            flash("Student added successfully.", "success")
            return redirect(url_for("dashboard"))
        return render_template("student_form.html", form=form, is_edit=False)

    @app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
    @login_required
    def edit_student(student_id):
        student = Student.query.get_or_404(student_id)
        form = StudentForm(obj=student)
        if form.validate_on_submit():
            # Ensure uniqueness when updating identifiers
            existing_id = Student.query.filter_by(student_id=form.student_id.data).first()
            existing_roll = Student.query.filter_by(roll_no=form.roll_no.data).first()
            if existing_id and existing_id.id != student.id:
                flash("Student ID already exists.", "warning")
                return render_template("student_form.html", form=form, is_edit=True)
            if existing_roll and existing_roll.id != student.id:
                flash("Roll number already exists.", "warning")
                return render_template("student_form.html", form=form, is_edit=True)

            student.student_id = form.student_id.data
            student.name = form.name.data
            student.roll_no = form.roll_no.data
            student.grade = form.grade.data
            db.session.commit()
            flash("Student updated.", "success")
            return redirect(url_for("dashboard"))
        return render_template("student_form.html", form=form, is_edit=True)

    @app.route("/students/<int:student_id>/delete", methods=["POST"])
    @login_required
    def delete_student(student_id):
        student = Student.query.get_or_404(student_id)
        db.session.delete(student)
        db.session.commit()
        flash("Student deleted.", "info")
        return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
