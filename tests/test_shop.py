"""Functional and security tests for products and the cart (Stage 3)."""
import re
from pathlib import Path

import pytest

from conftest import get_csrf_token, product_id

MUG = "SKU-MUG-001"        # 1299 cents, stock 50
HEADPHONES = "SKU-HDP-007"  # 5499 cents, stock 10
STICKERS = "SKU-STK-003"    # 599 cents, stock 200
PENS = "SKU-PEN-008"        # out of stock

ROOT = Path(__file__).resolve().parent.parent


def post(client, path, data, token=True):
    data = dict(data)
    if token is True:
        data["csrf_token"] = get_csrf_token(client)
    return client.post(path, data=data)


def cart_total_text(client):
    return client.get("/cart").get_data(as_text=True)


# ---------------- product listing / detail ----------------

def test_listing_shows_all_products_with_prices(shop):
    html = shop.get("/products").get_data(as_text=True)
    assert shop.get("/").status_code == 200
    for name in ("Rubber Duck Mug", "Desk Lamp", "Sticker Pack"):
        assert name in html
    assert "$12.99" in html and "$54.99" in html


def test_listing_marks_out_of_stock_without_add_button(shop, seeded_db):
    html = shop.get("/products").get_data(as_text=True)
    assert "Out of stock" in html
    pens = product_id(seeded_db, PENS)
    assert f'name="product_id" value="{pens}"' not in html


def test_detail_page_shows_product(shop, seeded_db):
    pid = product_id(seeded_db, MUG)
    resp = shop.get(f"/products/{pid}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Rubber Duck Mug" in html and "$12.99" in html and "SKU-MUG-001" in html


@pytest.mark.parametrize("path", [
    "/products/999999", "/products/0", "/products/-1", "/products/abc",
    "/products/1%20OR%201=1", "/products/1;DROP%20TABLE%20products",
    "/products/99999999999999999999999",
])
def test_detail_invalid_ids_return_404_not_500(shop, path):
    assert shop.get(path).status_code == 404


def test_products_table_survives_injection_style_paths(shop, seeded_db):
    shop.get("/products/1;DROP%20TABLE%20products")
    assert seeded_db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 8


# ---------------- cart basics ----------------

def test_empty_cart_page(shop):
    html = shop.get("/cart").get_data(as_text=True)
    assert "Your cart is empty" in html


def test_add_to_cart_and_total_from_database(shop, seeded_db):
    pid = product_id(seeded_db, MUG)
    resp = post(shop, "/cart/add", {"product_id": pid, "quantity": "3"})
    assert resp.status_code == 302
    html = cart_total_text(shop)
    assert "Rubber Duck Mug" in html
    assert "$38.97" in html  # 3 x 1299 cents


def test_adding_same_product_accumulates(shop, seeded_db):
    pid = product_id(seeded_db, MUG)
    post(shop, "/cart/add", {"product_id": pid, "quantity": "2"})
    post(shop, "/cart/add", {"product_id": pid, "quantity": "3"})
    assert "$64.95" in cart_total_text(shop)  # 5 x 1299


def test_cart_total_with_multiple_products(shop, seeded_db):
    post(shop, "/cart/add", {"product_id": product_id(seeded_db, MUG), "quantity": "1"})
    post(shop, "/cart/add", {"product_id": product_id(seeded_db, HEADPHONES), "quantity": "2"})
    # 1299 + 2*5499 = 12297
    assert "$122.97" in cart_total_text(shop)


def test_header_badge_counts_items(shop, seeded_db):
    post(shop, "/cart/add", {"product_id": product_id(seeded_db, MUG), "quantity": "4"})
    assert '<span class="badge">4</span>' in shop.get("/products").get_data(as_text=True)


def test_update_quantity(shop, seeded_db):
    pid = product_id(seeded_db, MUG)
    post(shop, "/cart/add", {"product_id": pid, "quantity": "1"})
    assert post(shop, "/cart/update", {"product_id": pid, "quantity": "4"}).status_code == 302
    assert "$51.96" in cart_total_text(shop)  # 4 x 1299


def test_remove_item(shop, seeded_db):
    pid = product_id(seeded_db, MUG)
    post(shop, "/cart/add", {"product_id": pid, "quantity": "1"})
    assert post(shop, "/cart/remove", {"product_id": pid}).status_code == 302
    assert "Your cart is empty" in cart_total_text(shop)


def test_remove_missing_item_is_harmless(shop, seeded_db):
    pid = product_id(seeded_db, MUG)
    assert post(shop, "/cart/remove", {"product_id": pid}).status_code == 302


# ---------------- price manipulation (client-supplied prices ignored) ----------------

def test_client_supplied_price_fields_are_ignored(shop, seeded_db):
    pid = product_id(seeded_db, MUG)
    post(shop, "/cart/add", {
        "product_id": pid, "quantity": "2",
        "price": "0.01", "price_cents": "1", "unit_price_cents": "1", "total": "0.02",
    })
    html = cart_total_text(shop)
    assert "$25.98" in html  # 2 x 1299 from the database
    assert "$0.02" not in html and "$0.01" not in html


def test_price_change_in_database_is_reflected_in_cart(shop, seeded_db):
    pid = product_id(seeded_db, MUG)
    post(shop, "/cart/add", {"product_id": pid, "quantity": "1"})
    seeded_db.execute("UPDATE products SET price_cents = 2000 WHERE id = ?", (pid,))
    seeded_db.commit()
    assert "$20.00" in cart_total_text(shop)


# ---------------- validation ----------------

BAD_QUANTITIES = ["0", "-1", "101", "abc", "", " ", "1.5", "1e2", "+5", "5; DROP", "١٢", "9999999999999999"]


@pytest.mark.parametrize("qty", BAD_QUANTITIES)
def test_add_rejects_bad_quantities(shop, seeded_db, qty):
    pid = product_id(seeded_db, MUG)
    resp = post(shop, "/cart/add", {"product_id": pid, "quantity": qty})
    assert resp.status_code == 400
    assert "Your cart is empty" in cart_total_text(shop)


def test_add_rejects_missing_fields(shop):
    assert post(shop, "/cart/add", {}).status_code == 400
    assert post(shop, "/cart/add", {"product_id": "1"}).status_code == 400


@pytest.mark.parametrize("pid", ["0", "-1", "abc", "", "1 OR 1=1", "1.0", "99999999999999999999"])
def test_add_rejects_bad_product_ids(shop, pid):
    resp = post(shop, "/cart/add", {"product_id": pid, "quantity": "1"})
    assert resp.status_code == 400
    assert "Your cart is empty" in cart_total_text(shop)


def test_add_unknown_product_returns_404(shop):
    assert post(shop, "/cart/add", {"product_id": "999999", "quantity": "1"}).status_code == 404
    assert "Your cart is empty" in cart_total_text(shop)


def test_cannot_add_out_of_stock_product(shop, seeded_db):
    resp = post(shop, "/cart/add", {"product_id": product_id(seeded_db, PENS), "quantity": "1"})
    assert resp.status_code == 400
    assert "Your cart is empty" in cart_total_text(shop)


def test_cannot_exceed_stock(shop, seeded_db):
    pid = product_id(seeded_db, HEADPHONES)  # stock 10
    assert post(shop, "/cart/add", {"product_id": pid, "quantity": "11"}).status_code == 400
    assert post(shop, "/cart/add", {"product_id": pid, "quantity": "10"}).status_code == 302
    assert post(shop, "/cart/add", {"product_id": pid, "quantity": "1"}).status_code == 400
    assert "$549.90" in cart_total_text(shop)  # still exactly 10 x 5499


def test_cumulative_quantity_cannot_exceed_100(shop, seeded_db):
    pid = product_id(seeded_db, STICKERS)  # stock 200, limit 100
    assert post(shop, "/cart/add", {"product_id": pid, "quantity": "100"}).status_code == 302
    assert post(shop, "/cart/add", {"product_id": pid, "quantity": "1"}).status_code == 400
    assert "$599.00" in cart_total_text(shop)  # 100 x 599


def test_update_rejects_invalid_values(shop, seeded_db):
    pid = product_id(seeded_db, MUG)
    post(shop, "/cart/add", {"product_id": pid, "quantity": "2"})
    for qty in ("0", "-5", "101", "x", ""):
        assert post(shop, "/cart/update", {"product_id": pid, "quantity": qty}).status_code == 400
    assert "$25.98" in cart_total_text(shop)  # unchanged: 2 x 1299


def test_update_above_stock_rejected(shop, seeded_db):
    pid = product_id(seeded_db, HEADPHONES)
    post(shop, "/cart/add", {"product_id": pid, "quantity": "1"})
    assert post(shop, "/cart/update", {"product_id": pid, "quantity": "11"}).status_code == 400


def test_update_item_not_in_cart_rejected(shop, seeded_db):
    pid = product_id(seeded_db, MUG)
    assert post(shop, "/cart/update", {"product_id": pid, "quantity": "1"}).status_code == 404


def test_remove_rejects_invalid_product_id(shop):
    assert post(shop, "/cart/remove", {"product_id": "abc"}).status_code == 400


def test_tampered_session_cart_is_sanitized(shop, seeded_db):
    """Even a hand-edited cart (negative, junk keys, huge, unknown product) is cleaned."""
    with shop.session_transaction() as sess:
        sess["cart"] = {"1": -5, "abc": 3, "2": 9999, "999999": 1, "3": True, "4": "7"}
    resp = shop.get("/cart")
    assert resp.status_code == 200
    assert "Your cart is empty" in resp.get_data(as_text=True)


def test_session_cart_stores_no_prices(shop, seeded_db):
    post(shop, "/cart/add", {"product_id": product_id(seeded_db, MUG), "quantity": "2"})
    with shop.session_transaction() as sess:
        assert all(isinstance(k, str) and isinstance(v, int) for k, v in sess["cart"].items())
        assert "total" not in sess and "price" not in str(sess["cart"]).lower()


# ---------------- CSRF ----------------

@pytest.mark.parametrize("path,data", [
    ("/cart/add", {"product_id": "1", "quantity": "1"}),
    ("/cart/update", {"product_id": "1", "quantity": "1"}),
    ("/cart/remove", {"product_id": "1"}),
])
def test_cart_posts_require_csrf_token(shop, path, data):
    assert post(shop, path, data, token=False).status_code == 400


def test_csrf_blocked_add_does_not_change_cart(shop, seeded_db):
    post(shop, "/cart/add", {"product_id": product_id(seeded_db, MUG), "quantity": "1"}, token=False)
    assert "Your cart is empty" in cart_total_text(shop)


def test_bad_csrf_token_rejected(shop):
    resp = shop.post("/cart/add", data={"product_id": "1", "quantity": "1", "csrf_token": "forged"})
    assert resp.status_code == 400


def test_rendered_forms_contain_csrf_tokens(shop, seeded_db):
    pid = product_id(seeded_db, MUG)
    post(shop, "/cart/add", {"product_id": pid, "quantity": "1"})
    pages = [shop.get("/products"), shop.get(f"/products/{pid}"), shop.get("/cart")]
    for page in pages:
        html = page.get_data(as_text=True)
        forms = len(re.findall(r'<form method="post"', html))
        tokens = len(re.findall(r'name="csrf_token"', html))
        assert forms >= 1 and tokens == forms


def test_cart_actions_are_post_only(shop):
    for path in ("/cart/add", "/cart/update", "/cart/remove"):
        assert shop.get(path).status_code == 405


# ---------------- output encoding (XSS) ----------------

XSS_NAME = "<script>alert(1)</script>"
XSS_DESC = '"><img src=x onerror=alert(2)>'


def _insert_hostile_product(db):
    cur = db.execute(
        "INSERT INTO products (sku, name, description, price_cents, stock) VALUES (?,?,?,?,?)",
        ("SKU-XSS-999", XSS_NAME, XSS_DESC, 100, 5),
    )
    db.commit()
    return cur.lastrowid


def test_product_fields_are_html_escaped_everywhere(shop, seeded_db):
    pid = _insert_hostile_product(seeded_db)
    post(shop, "/cart/add", {"product_id": pid, "quantity": "1"})
    for path in ("/products", f"/products/{pid}", "/cart"):
        html = shop.get(path).get_data(as_text=True)
        assert "<script>alert(1)" not in html
        assert "<img src=x" not in html
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_error_pages_do_not_reflect_user_input(shop):
    payload = "<script>alert(3)</script>"
    for data in ({"product_id": payload, "quantity": "1"}, {"product_id": "1", "quantity": payload}):
        html = post(shop, "/cart/add", data).get_data(as_text=True)
        assert payload not in html and "alert(3)" not in html


def test_unknown_route_page_has_no_stack_trace_or_input(shop):
    resp = shop.get("/nope<script>alert(4)</script>")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 404
    assert "alert(4)" not in html and "Traceback" not in html


# ---------------- sensitive data / hygiene ----------------

def test_pages_do_not_leak_secrets_or_hashes(shop, app, seeded_db):
    secret = app.config["SECRET_KEY"]
    pid = product_id(seeded_db, MUG)
    post(shop, "/cart/add", {"product_id": pid, "quantity": "1"})
    for path in ("/products", f"/products/{pid}", "/cart", "/missing"):
        html = shop.get(path).get_data(as_text=True)
        assert secret not in html
        assert "scrypt:" not in html and "password" not in html.lower()


def test_no_string_built_sql_in_app_code():
    """Static guard: SQL passed to execute() must never be an f-string, %-format or concat."""
    pattern = re.compile(r"execute(?:script)?\(\s*(f[\"']|[\"'][^\"']*[\"']\s*(%|\+)|.*\.format\()")
    offenders = []
    for path in (ROOT / "app").glob("*.py"):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.name}:{n}")
    assert not offenders, offenders


def test_templates_never_disable_autoescape():
    for path in (ROOT / "app" / "templates").glob("*.html"):
        text = path.read_text()
        assert "|safe" not in text and "| safe" not in text and "autoescape false" not in text
