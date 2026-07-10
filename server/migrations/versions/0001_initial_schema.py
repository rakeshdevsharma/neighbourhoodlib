"""initial schema: enums, books, book_copies, members, loans

Creates the core relational model for the neighbourhood library:
  - PostgreSQL ENUM types for copy status/condition and member status
  - books (catalog) and book_copies (physical items)
  - members (patrons) and loans (circulation records)
  - partial unique index ensuring at most one open loan per copy

Revision ID: 0001
Revises:
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

copy_status = postgresql.ENUM(
    "available", "on_loan", "lost", "damaged", "withdrawn", name="copy_status"
)
copy_condition = postgresql.ENUM("new", "good", "worn", name="copy_condition")
member_status = postgresql.ENUM("active", "suspended", name="member_status")


def upgrade() -> None:
    bind = op.get_bind()
    # Create ENUM types before tables that reference them.
    copy_status.create(bind, checkfirst=True)
    copy_condition.create(bind, checkfirst=True)
    member_status.create(bind, checkfirst=True)

    op.create_table(
        "books",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("author", sa.Text(), nullable=False),
        sa.Column("isbn", sa.Text(), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "book_copies",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "book_id",
            sa.BigInteger(),
            sa.ForeignKey("books.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("barcode", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="copy_status", create_type=False),
            nullable=False,
            server_default="available",
        ),
        sa.Column(
            "condition",
            postgresql.ENUM(name="copy_condition", create_type=False),
            nullable=True,
        ),
        sa.Column("shelf_location", sa.Text(), nullable=True),
        sa.Column("acquired_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_book_copies_book_id", "book_copies", ["book_id"])
    op.create_index("ix_book_copies_barcode", "book_copies", ["barcode"])

    op.create_table(
        "members",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False, unique=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="member_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "loans",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "copy_id", sa.BigInteger(), sa.ForeignKey("book_copies.id"), nullable=False
        ),
        sa.Column(
            "member_id", sa.BigInteger(), sa.ForeignKey("members.id"), nullable=False
        ),
        sa.Column("borrowed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fine_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("fine_cents >= 0", name="ck_loans_fine_nonneg"),
    )

    # A copy can have at most one OPEN loan (returned_at IS NULL). This partial
    # unique index is the DB-level guarantee against double-borrow.
    op.create_index(
        "one_open_loan_per_copy",
        "loans",
        ["copy_id"],
        unique=True,
        postgresql_where=sa.text("returned_at IS NULL"),
    )
    # Query accelerators.
    op.create_index(
        "ix_loans_member_open",
        "loans",
        ["member_id"],
        postgresql_where=sa.text("returned_at IS NULL"),
    )
    op.create_index(
        "ix_loans_due_open",
        "loans",
        ["due_at"],
        postgresql_where=sa.text("returned_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("loans")
    op.drop_table("members")
    op.drop_index("ix_book_copies_barcode", table_name="book_copies")
    op.drop_index("ix_book_copies_book_id", table_name="book_copies")
    op.drop_table("book_copies")
    op.drop_table("books")
    bind = op.get_bind()
    member_status.drop(bind, checkfirst=True)
    copy_condition.drop(bind, checkfirst=True)
    copy_status.drop(bind, checkfirst=True)
