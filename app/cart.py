"""Cart logic. The cart is stored in the signed session as {product_id: quantity}.

Security rules enforced here:
- The browser never supplies prices; totals are computed from the database only.
- Every product id and quantity is validated on the server.
- All SQL is parameterized.
"""
from flask import session

# Mirrors the CHECK constraint on order_items.quantity in schema.sql.
MAX_QTY_PER_ITEM = 100
# Product ids are small integers; anything bigger cannot exist (and would
# overflow SQLite's 64-bit integers).
MAX_PRODUCT_ID = 2**31 - 1
_MAX_INPUT_LEN = 9


class CartError(Exception):
    """A request the user must fix. Messages are fixed text, never user input."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


def parse_int(raw, label, minimum, maximum):
    """Strictly parse a base-10 positive integer string, or raise CartError.

    Rejects: non-strings, empty, signs ("-1", "+1"), decimals, exponents,
    non-ASCII digits, whitespace inside, and very long input.
    """
    if not isinstance(raw, str):
        raise CartError(f"Invalid {label}.")
    raw = raw.strip()
    if not raw or len(raw) > _MAX_INPUT_LEN or not (raw.isascii() and raw.isdigit()):
        raise CartError(f"Invalid {label}.")
    value = int(raw)
    if not minimum <= value <= maximum:
        raise CartError(f"Invalid {label}.")
    return value


def get_product(db, product_id):
    """Fetch one product by id using a parameterized query (or None)."""
    if not isinstance(product_id, int) or not 1 <= product_id <= MAX_PRODUCT_ID:
        return None
    return db.execute(
        "SELECT id, sku, name, description, price_cents, stock FROM products WHERE id = ?",
        (product_id,),
    ).fetchone()


def max_quantity_for(product):
    """Largest quantity allowed for a product: schema limit and available stock."""
    return min(MAX_QTY_PER_ITEM, product["stock"])


def _read_cart():
    """Return a sanitized copy of the session cart. Junk entries are dropped."""
    raw = session.get("cart")
    clean = {}
    if not isinstance(raw, dict):
        return clean
    for key, qty in raw.items():
        if (
            isinstance(key, str)
            and key.isascii()
            and key.isdigit()
            and len(key) <= _MAX_INPUT_LEN
            and isinstance(qty, int)
            and not isinstance(qty, bool)
            and 1 <= qty <= MAX_QTY_PER_ITEM
        ):
            clean[key] = qty
    return clean


def _save_cart(cart):
    session["cart"] = cart


def cart_count():
    """Total number of items in the cart (for the header badge). No DB access."""
    return sum(_read_cart().values())


def build_cart(db):
    """Return (lines, total_cents) computed from database prices only.

    Entries for products that no longer exist or are out of stock are removed,
    and quantities are clamped to current stock.
    """
    cart = _read_cart()
    lines = []
    total_cents = 0
    kept = {}
    for key, qty in cart.items():
        product = get_product(db, int(key))
        if product is None or product["stock"] <= 0:
            continue
        qty = min(qty, max_quantity_for(product))
        line_total = product["price_cents"] * qty
        lines.append({"product": product, "quantity": qty, "line_total_cents": line_total})
        total_cents += line_total
        kept[key] = qty
    if session.get("cart") is not None and kept != session["cart"]:
        _save_cart(kept)
    return lines, total_cents


def add_item(db, product_id_raw, quantity_raw):
    product_id = parse_int(product_id_raw, "product", 1, MAX_PRODUCT_ID)
    quantity = parse_int(quantity_raw, "quantity", 1, MAX_QTY_PER_ITEM)
    product = get_product(db, product_id)
    if product is None:
        raise CartError("Product not found.", 404)
    if product["stock"] <= 0:
        raise CartError("This product is out of stock.")
    cart = _read_cart()
    new_qty = cart.get(str(product_id), 0) + quantity
    if new_qty > max_quantity_for(product):
        raise CartError("That quantity is more than we can supply.")
    cart[str(product_id)] = new_qty
    _save_cart(cart)


def update_item(db, product_id_raw, quantity_raw):
    product_id = parse_int(product_id_raw, "product", 1, MAX_PRODUCT_ID)
    quantity = parse_int(quantity_raw, "quantity", 1, MAX_QTY_PER_ITEM)
    product = get_product(db, product_id)
    if product is None:
        raise CartError("Product not found.", 404)
    cart = _read_cart()
    if str(product_id) not in cart:
        raise CartError("That product is not in your cart.", 404)
    if quantity > max_quantity_for(product):
        raise CartError("That quantity is more than we can supply.")
    cart[str(product_id)] = quantity
    _save_cart(cart)


def remove_item(product_id_raw):
    product_id = parse_int(product_id_raw, "product", 1, MAX_PRODUCT_ID)
    cart = _read_cart()
    cart.pop(str(product_id), None)
    _save_cart(cart)


def export_cart():
    """Sanitized snapshot of the current cart (used to carry it across login)."""
    return _read_cart()


def restore_cart(saved):
    """Put a previously exported cart back into the (new) session."""
    if saved:
        _save_cart(saved)
