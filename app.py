import os
import sqlite3
import uuid
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from werkzeug.utils import secure_filename


# =====================================================
# 1. FLASK CONFIGURATION
# =====================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "change-this-secret-before-deployment"
)

app.config["DATABASE"] = os.path.join(
    app.root_path, "campus.db"
)

app.config["UPLOAD_FOLDER"] = os.path.join(
    app.root_path, "static", "uploads"
)

# Maximum request size: 5 MB
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "jpg", "jpeg", "png", "gif", "webp"
}

CATEGORIES = [
    "Books",
    "Calculators",
    "Notes",
    "Stationery",
    "Electronics",
    "Other"
]

CONDITIONS = [
    "New",
    "Like New",
    "Good",
    "Fair"
]

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# Admin credentials are configured through environment variables.
ADMIN_EMAIL = os.environ.get(
    "ADMIN_EMAIL", "admin@campusmart.com"
).strip().lower()

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")


# =====================================================
# 2. DATABASE CONNECTION
# =====================================================

def get_db():
    """Create a connection to the SQLite database."""

    connection = sqlite3.connect(
        app.config["DATABASE"]
    )

    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# =====================================================
# 3. CREATE DATABASE TABLES
# =====================================================

def init_db():
    """Create tables if they do not already exist."""

    with get_db() as db:

        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL CHECK(price >= 0),
                condition TEXT NOT NULL,
                description TEXT NOT NULL,
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (seller_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS contact_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                buyer_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (buyer_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,

                FOREIGN KEY (product_id)
                    REFERENCES products(id)
                    ON DELETE CASCADE
            );
        """)


# =====================================================
# 4. HELPER FUNCTIONS
# =====================================================

def allowed_file(filename):
    """Check the extension of an uploaded image."""

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def login_required(view):
    """Allow only logged-in students to access a route."""

    @wraps(view)
    def wrapped_view(**kwargs):

        if "user_id" not in session:
            flash("Please log in to continue.", "info")
            return redirect(url_for("login"))

        return view(**kwargs)

    return wrapped_view


def admin_required(view):
    """Allow only an authenticated admin to access a route."""

    @wraps(view)
    def wrapped_view(**kwargs):

        if not session.get("admin_logged_in"):
            flash("Please log in as admin.", "info")
            return redirect(url_for("admin_login"))

        return view(**kwargs)

    return wrapped_view


def delete_local_image(image_path):
    """Delete an image only if it belongs to the upload folder."""

    if not image_path:
        return

    # External URLs must never be treated as local files.
    if image_path.startswith(("http://", "https://")):
        return

    upload_folder = os.path.realpath(
        app.config["UPLOAD_FOLDER"]
    )

    image_file = os.path.realpath(
        os.path.join(
            app.root_path,
            "static",
            image_path
        )
    )

    try:
        if (
            os.path.commonpath(
                [upload_folder, image_file]
            ) == upload_folder
            and os.path.isfile(image_file)
        ):
            os.remove(image_file)

    except (ValueError, OSError):
        app.logger.warning(
            "Could not safely remove uploaded image."
        )


# =====================================================
# 5. HOME PAGE AND SEARCH
# =====================================================

@app.route("/")
def index():

    search = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()

    query = """
        SELECT
            products.*,
            users.name AS seller_name
        FROM products
        JOIN users
            ON products.seller_id = users.id
        WHERE 1 = 1
    """

    parameters = []

    # Search by product name or description.
    if search:
        query += """
            AND (
                products.name LIKE ?
                OR products.description LIKE ?
            )
        """

        parameters.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    # Filter by category.
    if category:
        if category in CATEGORIES:
            query += " AND products.category = ?"
            parameters.append(category)
        else:
            category = ""

    # Minimum price filter.
    if min_price:
        try:
            minimum = float(min_price)

            if minimum < 0:
                raise ValueError

            query += " AND products.price >= ?"
            parameters.append(minimum)

        except ValueError:
            min_price = ""
            flash("Enter a valid minimum price.", "error")

    # Maximum price filter.
    if max_price:
        try:
            maximum = float(max_price)

            if maximum < 0:
                raise ValueError

            query += " AND products.price <= ?"
            parameters.append(maximum)

        except ValueError:
            max_price = ""
            flash("Enter a valid maximum price.", "error")

    query += " ORDER BY products.created_at DESC"

    with get_db() as db:
        products = db.execute(
            query, parameters
        ).fetchall()

    return render_template(
        "index.html",
        products=products,
        categories=CATEGORIES,
        search=search,
        selected_category=category,
        min_price=min_price,
        max_price=max_price
    )


# =====================================================
# 6. STUDENT REGISTRATION
# =====================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get(
            "name", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        if not name or not email or not password:
            flash("Please complete all fields.", "error")
            return render_template("register.html")

        if len(name) > 100 or len(email) > 254:
            flash("Name or email is too long.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash(
                "Password must be at least 8 characters long.",
                "error"
            )
            return render_template("register.html")

        try:
            with get_db() as db:
                db.execute("""
                    INSERT INTO users
                        (name, email, password_hash)
                    VALUES (?, ?, ?)
                """, (
                    name,
                    email,
                    generate_password_hash(password)
                ))

            flash(
                "Account created successfully. Please log in.",
                "success"
            )

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash(
                "An account with that email already exists.",
                "error"
            )

    return render_template("register.html")


# =====================================================
# 7. STUDENT LOGIN
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        with get_db() as db:
            user = db.execute("""
                SELECT *
                FROM users
                WHERE email = ?
            """, (email,)).fetchone()

        if (
            user
            and check_password_hash(
                user["password_hash"], password
            )
        ):
            session.clear()

            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            flash(
                f"Welcome, {user['name']}!",
                "success"
            )

            return redirect(url_for("index"))

        flash("Incorrect email or password.", "error")

    return render_template("login.html")


# =====================================================
# 8. STUDENT LOGOUT
# =====================================================

@app.route("/logout", methods=["GET", "POST"])
def logout():

    session.clear()

    flash("You have been logged out.", "info")

    return redirect(url_for("index"))


# =====================================================
# 9. SELL AN ITEM WITH PHOTO UPLOAD
# =====================================================

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():

    if request.method == "POST":

        name = request.form.get(
            "name", ""
        ).strip()

        category = request.form.get(
            "category", ""
        ).strip()

        price_text = request.form.get(
            "price", ""
        ).strip()

        condition = request.form.get(
            "condition", ""
        ).strip()

        description = request.form.get(
            "description", ""
        ).strip()

        # Validate required fields.
        if (
            not name
            or not description
            or category not in CATEGORIES
            or condition not in CONDITIONS
        ):
            flash(
                "Please complete all required fields correctly.",
                "error"
            )

            return render_template(
                "sell.html",
                categories=CATEGORIES,
                conditions=CONDITIONS
            )

        if len(name) > 100 or len(description) > 1000:
            flash(
                "The item name or description is too long.",
                "error"
            )

            return render_template(
                "sell.html",
                categories=CATEGORIES,
                conditions=CONDITIONS
            )

        # Validate price.
        try:
            price = float(price_text)

            if not (0 <= price < 1_000_000_000):
                raise ValueError

        except (ValueError, OverflowError):
            flash(
                "Enter a valid non-negative price.",
                "error"
            )

            return render_template(
                "sell.html",
                categories=CATEGORIES,
                conditions=CONDITIONS
            )

        # Handle uploaded photo.
        image = request.files.get("photo")
        image_path = None
        saved_path = None

        if image and image.filename:

            if not allowed_file(image.filename):
                flash(
                    "Use a JPG, JPEG, PNG, GIF or WEBP image.",
                    "error"
                )

                return render_template(
                    "sell.html",
                    categories=CATEGORIES,
                    conditions=CONDITIONS
                )

            extension = image.filename.rsplit(
                ".", 1
            )[1].lower()

            unique_name = secure_filename(
                f"{uuid.uuid4().hex}.{extension}"
            )

            saved_path = os.path.join(
                app.config["UPLOAD_FOLDER"],
                unique_name
            )

            image_path = f"uploads/{unique_name}"

            try:
                image.save(saved_path)

                with get_db() as db:
                    db.execute("""
                        INSERT INTO products (
                            seller_id,
                            name,
                            category,
                            price,
                            condition,
                            description,
                            image_url
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        session["user_id"],
                        name,
                        category,
                        price,
                        condition,
                        description,
                        image_path
                    ))

            except Exception:
                if saved_path and os.path.isfile(saved_path):
                    os.remove(saved_path)

                app.logger.exception(
                    "Could not save product listing."
                )

                flash(
                    "Could not save the listing. Please try again.",
                    "error"
                )

                return render_template(
                    "sell.html",
                    categories=CATEGORIES,
                    conditions=CONDITIONS
                )

        else:
            # Save a listing without a photo.
            try:
                with get_db() as db:
                    db.execute("""
                        INSERT INTO products (
                            seller_id,
                            name,
                            category,
                            price,
                            condition,
                            description,
                            image_url
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        session["user_id"],
                        name,
                        category,
                        price,
                        condition,
                        description,
                        None
                    ))

            except sqlite3.Error:
                app.logger.exception(
                    "Could not save product listing."
                )

                flash(
                    "Could not save the listing. Please try again.",
                    "error"
                )

                return render_template(
                    "sell.html",
                    categories=CATEGORIES,
                    conditions=CONDITIONS
                )

        flash(
            "Your item has been listed successfully!",
            "success"
        )

        return redirect(url_for("index"))

    return render_template(
        "sell.html",
        categories=CATEGORIES,
        conditions=CONDITIONS
    )


# =====================================================
# 10. PRODUCT DETAILS AND CONTACT SELLER
# =====================================================

@app.route(
    "/product/<int:product_id>",
    methods=["GET", "POST"]
)
def product_detail(product_id):

    with get_db() as db:
        product = db.execute("""
            SELECT
                products.*,
                users.name AS seller_name,
                users.email AS seller_email
            FROM products
            JOIN users
                ON products.seller_id = users.id
            WHERE products.id = ?
        """, (product_id,)).fetchone()

    if product is None:
        abort(404)

    if request.method == "POST":

        if "user_id" not in session:
            flash(
                "Please log in before contacting a seller.",
                "info"
            )

            return redirect(url_for("login"))

        if session["user_id"] == product["seller_id"]:
            flash(
                "You cannot contact yourself about your own listing.",
                "error"
            )

            return redirect(
                url_for(
                    "product_detail",
                    product_id=product_id
                )
            )

        message = request.form.get(
            "message", ""
        ).strip()

        if not message:
            flash(
                "Please enter a message.",
                "error"
            )

        elif len(message) > 1000:
            flash(
                "Your message must be 1000 characters or fewer.",
                "error"
            )

        else:
            with get_db() as db:
                db.execute("""
                    INSERT INTO contact_requests (
                        buyer_id,
                        product_id,
                        message
                    )
                    VALUES (?, ?, ?)
                """, (
                    session["user_id"],
                    product_id,
                    message
                ))

            flash(
                "Your contact request has been saved.",
                "success"
            )

            return redirect(
                url_for(
                    "product_detail",
                    product_id=product_id
                )
            )

    return render_template(
        "product.html",
        product=product
    )


# =====================================================
# 11. ADMIN LOGIN
# =====================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if session.get("admin_logged_in"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get(
            "password", ""
        )

        if not ADMIN_PASSWORD:
            flash(
                "Admin password is not configured. "
                "Set the ADMIN_PASSWORD environment variable.",
                "error"
            )

            return render_template("admin_login.html")

        if (
            email == ADMIN_EMAIL
            and password == ADMIN_PASSWORD
        ):
            session.clear()

            session["admin_logged_in"] = True
            session["admin_email"] = ADMIN_EMAIL

            flash(
                "Admin login successful.",
                "success"
            )

            return redirect(
                url_for("admin_dashboard")
            )

        flash(
            "Invalid admin email or password.",
            "error"
        )

    return render_template("admin_login.html")


# =====================================================
# 12. ADMIN DASHBOARD
# =====================================================

@app.route("/admin")
@admin_required
def admin_dashboard():

    with get_db() as db:

        # Total registered students.
        total_users = db.execute("""
            SELECT COUNT(*)
            FROM users
        """).fetchone()[0]

        # Total product listings.
        total_products = db.execute("""
            SELECT COUNT(*)
            FROM products
        """).fetchone()[0]

        # Total contact requests.
        total_contacts = db.execute("""
            SELECT COUNT(*)
            FROM contact_requests
        """).fetchone()[0]

        # All registered users.
        users = db.execute("""
            SELECT
                id,
                name,
                email,
                created_at
            FROM users
            ORDER BY id DESC
        """).fetchall()

        # All product listings.
        products = db.execute("""
            SELECT
                products.*,
                users.name AS seller_name
            FROM products
            JOIN users
                ON products.seller_id = users.id
            ORDER BY products.id DESC
        """).fetchall()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_products=total_products,
        total_contacts=total_contacts,
        users=users,
        products=products
    )


# =====================================================
# 13. ADMIN DELETE PRODUCT
# =====================================================

@app.route(
    "/admin/product/delete/<int:product_id>",
    methods=["POST"]
)
@admin_required
def admin_delete_product(product_id):

    with get_db() as db:

        product = db.execute("""
            SELECT id, image_url
            FROM products
            WHERE id = ?
        """, (product_id,)).fetchone()

        if product is None:
            flash(
                "Listing not found.",
                "error"
            )

            return redirect(
                url_for("admin_dashboard")
            )

        image_path = product["image_url"]

        db.execute("""
            DELETE FROM products
            WHERE id = ?
        """, (product_id,))

    # Delete its uploaded photo after deleting the listing.
    delete_local_image(image_path)

    flash(
        "Listing deleted successfully.",
        "success"
    )

    return redirect(
        url_for("admin_dashboard")
    )


# =====================================================
# 14. ADMIN LOGOUT
# =====================================================

@app.route(
    "/admin/logout",
    methods=["POST"]
)
@admin_required
def admin_logout():

    session.clear()

    flash(
        "Admin logged out successfully.",
        "info"
    )

    return redirect(
        url_for("admin_login")
    )


# =====================================================
# 15. ERROR HANDLERS
# =====================================================

@app.errorhandler(404)
def page_not_found(error):

    return render_template("404.html"), 404


@app.errorhandler(413)
def file_too_large(error):

    flash(
        "The uploaded file is too large. Maximum size is 5 MB.",
        "error"
    )

    return redirect(url_for("sell"))


# =====================================================
# 16. INITIALIZE DATABASE AND RUN APPLICATION
# =====================================================

init_db()


if __name__ == "__main__":

    app.run(debug=True)