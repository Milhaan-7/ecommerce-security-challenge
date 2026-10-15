"""Storefront routes: product listing, product detail, and cart."""
from flask import Blueprint, redirect, render_template, request, url_for, abort

from . import cart
from .db import get_db

bp = Blueprint("shop", __name__)


@bp.get("/")
@bp.get("/products")
def products():
    rows = get_db().execute(
        "SELECT id, sku, name, description, price_cents, stock FROM products ORDER BY id"
    ).fetchall()
    by_sku = {row["sku"]: row for row in rows}
    return render_template("products.html", products=rows, by_sku=by_sku)


@bp.get("/products/<int:product_id>")
def product_detail(product_id):
    product = cart.get_product(get_db(), product_id)
    if product is None:
        abort(404)
    return render_template(
        "product_detail.html",
        product=product,
        max_qty=cart.max_quantity_for(product),
    )


@bp.get("/cart")
def view_cart():
    lines, total_cents = cart.build_cart(get_db())
    return render_template("cart.html", lines=lines, total_cents=total_cents)


# NOTE: the forms below post only a product id and a quantity. Any other field a
# browser sends (for example a "price") is never read.
@bp.post("/cart/add")
def add_to_cart():
    cart.add_item(get_db(), request.form.get("product_id"), request.form.get("quantity"))
    return redirect(url_for("shop.view_cart"))


@bp.post("/cart/update")
def update_cart():
    cart.update_item(get_db(), request.form.get("product_id"), request.form.get("quantity"))
    return redirect(url_for("shop.view_cart"))


@bp.post("/cart/remove")
def remove_from_cart():
    cart.remove_item(request.form.get("product_id"))
    return redirect(url_for("shop.view_cart"))
