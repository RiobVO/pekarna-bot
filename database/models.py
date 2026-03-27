from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Client(Base):
    """Информация о клиенте"""
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    contact_name = Column(String, nullable=False)    # имя контактного лица
    organization = Column(String, nullable=False)    # название организации
    phone = Column(String, nullable=False)           # номер телефона
    inn = Column(String, nullable=True)              # ИНН — 9 цифр
    bank_account = Column(String, nullable=True)     # Расчётный счёт — 20 цифр
    mfo = Column(String, nullable=True)              # МФО банка — 5 цифр
    bank_name = Column(String, nullable=True)        # Название банка
    legal_address = Column(String, nullable=True)    # Юридический/фактический адрес


class Product(Base):
    """Продукты которые можно заказать"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=False)


class Order(Base):
    """Заказ от клиента"""
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    delivery_date = Column(String, nullable=False)
    delivery_time = Column(String, nullable=False)
    delivery_type = Column(String, nullable=False, default="delivery")  # delivery/pickup
    status = Column(String, default="new")
    created_at = Column(DateTime, default=datetime.now)
    comment = Column(String, nullable=True)
    delivery_address = Column(String, nullable=True)
    status_message_id = Column(Integer, nullable=True)

    items = relationship("OrderItem", back_populates="order")
    client = relationship("Client")


class OrderItem(Base):
    """Позиции внутри заказа"""
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_name = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="items")

class ClientPrice(Base):
    """Индивидуальные цены для клиентов"""
    __tablename__ = "client_prices"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    price = Column(Integer, nullable=False)