import React from "react";
import "../styles/ProductGrid.css";

function ProductCard({ product }) {
  const stock = parseInt(product.stock);

  const getStockClass = (s) => {
    if (s <= 0) return "stock-out";
    if (s < 10) return "stock-low";
    return "stock-ok";
  };

  const getStockLabel = (s) => {
    if (s <= 0) return "Out of stock";
    if (s < 10) return `Low stock: ${s}`;
    return `In stock: ${s}`;
  };

  return (
    <div className="product-card">
      <div className="product-name">{product.name}</div>
      <div className="product-fitment">{product.vehicle_fitment}</div>

      <div className="product-meta">
        <span className="chip">{product.sku}</span>
        <span className="chip">{product.brand}</span>
        <span className={`stock-badge ${getStockClass(stock)}`}>
          {getStockLabel(stock)}
        </span>
      </div>

      <div className="price-row">
        <div className="price">
          INR {parseInt(product.price_inr).toLocaleString("en-IN")}
        </div>
        <div className="product-category">{product.category}</div>
      </div>
    </div>
  );
}

function ProductGrid({ products }) {
  if (!products || products.length === 0) {
    return null;
  }

  return (
    <div className="product-grid">
      {products.map((product, idx) => (
        <ProductCard key={idx} product={product} />
      ))}
    </div>
  );
}

export default ProductGrid;
