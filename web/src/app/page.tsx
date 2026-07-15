"use client";

/**
 * Main library admin UI — a tabbed single page that talks to the backend via
 * gRPC-Web (through Envoy). Each tab is a self-contained section with its own
 * forms, list view, and success/error banners.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { client, grpcMessage, pb } from "@/lib/client";

type Tab = "books" | "members" | "loans";

/** Root page: tab switcher that renders one of three admin sections. */
export default function Home() {
  const [tab, setTab] = useState<Tab>("books");
  return (
    <main>
      <h1>Neighborhood Library</h1>
      <div className="muted">Manage books, copies, members, and lending.</div>
      <div className="tabs">
        {(["books", "members", "loans"] as Tab[]).map((t) => (
          <button
            key={t}
            className={tab === t ? "active" : ""}
            onClick={() => setTab(t)}
          >
            {t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === "books" && <BooksSection />}
      {tab === "members" && <MembersSection />}
      {tab === "loans" && <LoansSection />}
    </main>
  );
}

/** Shared flash banner state for success and gRPC error messages. */
function useBanner() {
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  /** Clear both banners, then run an async action (keeps UI from showing stale messages). */
  const show = (fn: () => void) => {
    setError("");
    setOk("");
    fn();
  };
  return { error, ok, setError, setOk, show };
}

/** Searchable picker: type to see matches, click one to select. */
function SearchPicker<T>({
  label,
  placeholder,
  query,
  onQueryChange,
  selected,
  onSelect,
  options,
  getKey,
  formatSelected,
  renderOption,
  emptyHint = "No matches",
}: {
  label: string;
  placeholder: string;
  query: string;
  onQueryChange: (q: string) => void;
  selected: T | null;
  onSelect: (item: T | null) => void;
  options: T[];
  getKey: (item: T) => string | number;
  formatSelected: (item: T) => string;
  renderOption: (item: T) => ReactNode;
  emptyHint?: string;
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  const pick = (item: T) => {
    onSelect(item);
    setOpen(false);
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    const next = e.relatedTarget as Node | null;
    if (next && wrapRef.current?.contains(next)) return;
    setOpen(false);
  };

  if (selected) {
    return (
      <div className="picker">
        <span className="picker-label">{label}</span>
        <div className="picker-selected">
          <span>{formatSelected(selected)}</span>
          <button
            type="button"
            className="small"
            onClick={() => {
              onSelect(null);
              onQueryChange("");
              setOpen(true);
            }}
          >
            Change
          </button>
        </div>
      </div>
    );
  }

  const trimmed = query.trim();
  const showResults = open && trimmed.length > 0;

  return (
    <div className="picker" ref={wrapRef}>
      <span className="picker-label">{label}</span>
      <input
        placeholder={placeholder}
        value={query}
        onChange={(e) => {
          onQueryChange(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={handleBlur}
        autoComplete="off"
      />
      {showResults && (
        <div
          className="picker-results"
          onMouseDown={(e) => e.preventDefault()}
        >
          {options.length === 0 ? (
            <div className="picker-empty muted">{emptyHint}</div>
          ) : (
            options.map((item) => (
              <button
                key={getKey(item)}
                type="button"
                className="picker-option"
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(item);
                }}
              >
                {renderOption(item)}
              </button>
            ))
          )}
        </div>
      )}
      {open && trimmed.length === 0 && (
        <div className="picker-results" onMouseDown={(e) => e.preventDefault()}>
          <div className="picker-empty muted">Type to search…</div>
        </div>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Books — catalog titles, add copies, list availability
// --------------------------------------------------------------------------- //
/** Books tab: create titles, add shelf copies, list availability via gRPC-Web. */
function BooksSection() {
  const [books, setBooks] = useState<pb.Book.AsObject[]>([]);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [isbn, setIsbn] = useState("");
  const [editingBook, setEditingBook] = useState<pb.Book.AsObject | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editAuthor, setEditAuthor] = useState("");
  const [editIsbn, setEditIsbn] = useState("");
  const [copyBookId, setCopyBookId] = useState<number | null>(null);
  const [barcode, setBarcode] = useState("");
  const [shelf, setShelf] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const b = useBanner();

  /** Fetch all books from the server (page_size=100) and refresh local state. */
  const load = useCallback(async () => {
    try {
      const req = new pb.ListBooksRequest();
      req.setPageSize(100);
      const res = await client.listBooks(req);
      setBooks(res.getBooksList().map((x) => x.toObject()));
    } catch (e) {
      b.setError(grpcMessage(e));
    }
  }, []); // eslint-disable-line

  useEffect(() => {
    load();
  }, [load]);

  /** POST CreateBook via grpc-web, then clear the form and reload the table. */
  const createBook = async (e: React.FormEvent) => {
    e.preventDefault();
    b.show(() => {});
    const t = title.trim();
    const a = author.trim();
    if (!t || !a) {
      b.setError("Title and author are required.");
      return;
    }
    setSubmitting(true);
    try {
      const req = new pb.CreateBookRequest();
      req.setTitle(t);
      req.setAuthor(a);
      req.setIsbn(isbn.trim());
      await client.createBook(req);
      setTitle("");
      setAuthor("");
      setIsbn("");
      b.setOk("Book created.");
      load();
    } catch (e) {
      b.setError(grpcMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  const startEditBook = (bk: pb.Book.AsObject) => {
    b.show(() => {});
    setEditingBook(bk);
    setEditTitle(bk.title);
    setEditAuthor(bk.author);
    setEditIsbn(bk.isbn);
  };

  const cancelEditBook = () => {
    setEditingBook(null);
    setEditTitle("");
    setEditAuthor("");
    setEditIsbn("");
  };

  /** POST UpdateBook for the selected catalog row. */
  const updateBook = async (e: React.FormEvent) => {
    e.preventDefault();
    b.show(() => {});
    if (!editingBook) return;
    const t = editTitle.trim();
    const a = editAuthor.trim();
    if (!t || !a) {
      b.setError("Title and author are required.");
      return;
    }
    setSubmitting(true);
    try {
      const req = new pb.UpdateBookRequest();
      req.setId(editingBook.id);
      req.setTitle(t);
      req.setAuthor(a);
      req.setIsbn(editIsbn.trim());
      await client.updateBook(req);
      cancelEditBook();
      b.setOk("Book updated.");
      load();
    } catch (e) {
      b.setError(grpcMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  /** POST AddCopy for the selected book; barcode must be globally unique. */
  const addCopy = async (e: React.FormEvent) => {
    e.preventDefault();
    b.show(() => {});
    if (!copyBookId) return;
    const code = barcode.trim();
    if (!code) {
      b.setError("Barcode is required.");
      return;
    }
    setSubmitting(true);
    try {
      const req = new pb.AddCopyRequest();
      req.setBookId(copyBookId);
      req.setBarcode(code);
      req.setCondition(pb.CopyCondition.COPY_CONDITION_GOOD);
      req.setShelfLocation(shelf.trim());
      await client.addCopy(req);
      setBarcode("");
      setShelf("");
      b.setOk("Copy added.");
      load();
    } catch (e) {
      b.setError(grpcMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  /** True once any edit field differs from the book being edited (whitespace-insensitive). */
  const bookDirty =
    !!editingBook &&
    (editTitle.trim() !== editingBook.title ||
      editAuthor.trim() !== editingBook.author ||
      editIsbn.trim() !== editingBook.isbn);
  /** Edit form has the required fields filled (ignoring whitespace). */
  const bookEditValid = !!editTitle.trim() && !!editAuthor.trim();

  return (
    <div>
      {b.error && <div className="error">{b.error}</div>}
      {b.ok && <div className="ok-banner">{b.ok}</div>}

      <div className="card">
        <h2>Add a book</h2>
        <form className="row" onSubmit={createBook}>
          <label>
            Title
            <input value={title} onChange={(e) => setTitle(e.target.value)} required />
          </label>
          <label>
            Author
            <input value={author} onChange={(e) => setAuthor(e.target.value)} required />
          </label>
          <label>
            ISBN (optional)
            <input value={isbn} onChange={(e) => setIsbn(e.target.value)} />
          </label>
          <button
            className="primary"
            type="submit"
            disabled={submitting || !title.trim() || !author.trim()}
          >
            Create
          </button>
        </form>
      </div>

      {editingBook && (
        <div className="card">
          <h2>Edit book #{editingBook.id}</h2>
          <form className="row" onSubmit={updateBook}>
            <label>
              Title
              <input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} required />
            </label>
            <label>
              Author
              <input value={editAuthor} onChange={(e) => setEditAuthor(e.target.value)} required />
            </label>
            <label>
              ISBN (optional)
              <input value={editIsbn} onChange={(e) => setEditIsbn(e.target.value)} />
            </label>
            <button
              className="primary"
              type="submit"
              disabled={submitting || !bookDirty || !bookEditValid}
            >
              Save
            </button>
            <button type="button" className="small" onClick={cancelEditBook}>Cancel</button>
          </form>
        </div>
      )}

      <div className="card">
        <h2>Add a copy</h2>
        <form className="row" onSubmit={addCopy}>
          <label>
            Book
            <select
              value={copyBookId ?? ""}
              onChange={(e) => setCopyBookId(Number(e.target.value) || null)}
              required
            >
              <option value="">Select…</option>
              {books.map((bk) => (
                <option key={bk.id} value={bk.id}>
                  {bk.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Barcode
            <input value={barcode} onChange={(e) => setBarcode(e.target.value)} required />
          </label>
          <label>
            Shelf
            <input value={shelf} onChange={(e) => setShelf(e.target.value)} />
          </label>
          <button
            className="primary"
            type="submit"
            disabled={submitting || !copyBookId || !barcode.trim()}
          >
            Add copy
          </button>
        </form>
      </div>

      <div className="card">
        <h2>Books</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Author</th>
              <th>ISBN</th>
              <th>Available / Total</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {books.map((bk) => (
              <tr key={bk.id}>
                <td>{bk.id}</td>
                <td>{bk.title}</td>
                <td>{bk.author}</td>
                <td>{bk.isbn || "—"}</td>
                <td>
                  <span className={bk.availableCopies > 0 ? "pill ok" : "pill bad"}>
                    {bk.availableCopies} / {bk.totalCopies}
                  </span>
                </td>
                <td>
                  <button type="button" className="small" onClick={() => startEditBook(bk)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))}
            {books.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">No books yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Members — register patrons and list membership status
// --------------------------------------------------------------------------- //
/** Members tab: register patrons and display ACTIVE/SUSPENDED status. */
function MembersSection() {
  const [members, setMembers] = useState<pb.Member.AsObject[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [editingMember, setEditingMember] = useState<pb.Member.AsObject | null>(null);
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editStatus, setEditStatus] = useState<number>(pb.MemberStatus.MEMBER_STATUS_ACTIVE);
  const [submitting, setSubmitting] = useState(false);
  const b = useBanner();

  /** Fetch all members (page_size=100) for the table below. */
  const load = useCallback(async () => {
    try {
      const req = new pb.ListMembersRequest();
      req.setPageSize(100);
      const res = await client.listMembers(req);
      setMembers(res.getMembersList().map((x) => x.toObject()));
    } catch (e) {
      b.setError(grpcMessage(e));
    }
  }, []); // eslint-disable-line

  useEffect(() => {
    load();
  }, [load]);

  const startEditMember = (m: pb.Member.AsObject) => {
    b.show(() => {});
    setEditingMember(m);
    setEditName(m.name);
    setEditEmail(m.email);
    setEditPhone(m.phone);
    setEditStatus(m.status);
  };

  const cancelEditMember = () => {
    setEditingMember(null);
    setEditName("");
    setEditEmail("");
    setEditPhone("");
    setEditStatus(pb.MemberStatus.MEMBER_STATUS_ACTIVE);
  };

  /** POST UpdateMember; email uniqueness and status changes are enforced server-side. */
  const updateMember = async (e: React.FormEvent) => {
    e.preventDefault();
    b.show(() => {});
    if (!editingMember) return;
    const n = editName.trim();
    const em = editEmail.trim();
    if (!n || !em) {
      b.setError("Name and email are required.");
      return;
    }
    setSubmitting(true);
    try {
      const req = new pb.UpdateMemberRequest();
      req.setId(editingMember.id);
      req.setName(n);
      req.setEmail(em);
      req.setPhone(editPhone.trim());
      req.setStatus(editStatus);
      await client.updateMember(req);
      cancelEditMember();
      b.setOk("Member updated.");
      load();
    } catch (e) {
      b.setError(grpcMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  /** POST CreateMember; email uniqueness is enforced server-side. */
  const createMember = async (e: React.FormEvent) => {
    e.preventDefault();
    b.show(() => {});
    const n = name.trim();
    const em = email.trim();
    if (!n || !em) {
      b.setError("Name and email are required.");
      return;
    }
    setSubmitting(true);
    try {
      const req = new pb.CreateMemberRequest();
      req.setName(n);
      req.setEmail(em);
      req.setPhone(phone.trim());
      await client.createMember(req);
      setName("");
      setEmail("");
      setPhone("");
      b.setOk("Member created.");
      load();
    } catch (e) {
      b.setError(grpcMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  /** Map protobuf MemberStatus enum to a human-readable label. */
  const statusLabel = (s: number) =>
    s === pb.MemberStatus.MEMBER_STATUS_ACTIVE ? "active" : "suspended";

  /** True once any edit field differs from the member being edited (whitespace-insensitive for text). */
  const memberDirty =
    !!editingMember &&
    (editName.trim() !== editingMember.name ||
      editEmail.trim() !== editingMember.email ||
      editPhone.trim() !== editingMember.phone ||
      editStatus !== editingMember.status);
  /** Edit form has the required fields filled (ignoring whitespace). */
  const memberEditValid = !!editName.trim() && !!editEmail.trim();

  return (
    <div>
      {b.error && <div className="error">{b.error}</div>}
      {b.ok && <div className="ok-banner">{b.ok}</div>}

      <div className="card">
        <h2>Add a member</h2>
        <form className="row" onSubmit={createMember}>
          <label>
            Name
            <input value={name} onChange={(e) => setName(e.target.value)} required />
          </label>
          <label>
            Email
            <input value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Phone
            <input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
          <button
            className="primary"
            type="submit"
            disabled={submitting || !name.trim() || !email.trim()}
          >
            Create
          </button>
        </form>
      </div>

      {editingMember && (
        <div className="card">
          <h2>Edit member #{editingMember.id}</h2>
          <form className="row" onSubmit={updateMember}>
            <label>
              Name
              <input value={editName} onChange={(e) => setEditName(e.target.value)} required />
            </label>
            <label>
              Email
              <input value={editEmail} onChange={(e) => setEditEmail(e.target.value)} required />
            </label>
            <label>
              Phone
              <input value={editPhone} onChange={(e) => setEditPhone(e.target.value)} />
            </label>
            <label>
              Status
              <select
                value={editStatus}
                onChange={(e) => setEditStatus(Number(e.target.value))}
              >
                <option value={pb.MemberStatus.MEMBER_STATUS_ACTIVE}>Active</option>
                <option value={pb.MemberStatus.MEMBER_STATUS_SUSPENDED}>Suspended</option>
              </select>
            </label>
            <button
              className="primary"
              type="submit"
              disabled={submitting || !memberDirty || !memberEditValid}
            >
              Save
            </button>
            <button type="button" className="small" onClick={cancelEditMember}>Cancel</button>
          </form>
        </div>
      )}

      <div className="card">
        <h2>Members</h2>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.id}>
                <td>{m.id}</td>
                <td>{m.name}</td>
                <td>{m.email}</td>
                <td>{m.phone || "—"}</td>
                <td>
                  <span className={m.status === pb.MemberStatus.MEMBER_STATUS_ACTIVE ? "pill ok" : "pill warn"}>
                    {statusLabel(m.status)}
                  </span>
                </td>
                <td>
                  <button type="button" className="small" onClick={() => startEditMember(m)}>
                    Edit
                  </button>
                </td>
              </tr>
            ))}
            {members.length === 0 && (
              <tr>
                <td colSpan={6} className="muted">No members yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Loans — borrow by member+book, return by loan id, filterable list
// --------------------------------------------------------------------------- //
/** Loans tab: borrow/return flows and a filterable loan history table. */
function LoansSection() {
  const [loans, setLoans] = useState<pb.Loan.AsObject[]>([]);
  const [members, setMembers] = useState<pb.Member.AsObject[]>([]);
  const [books, setBooks] = useState<pb.Book.AsObject[]>([]);
  const [filter, setFilter] = useState<number>(pb.LoanStatus.LOAN_STATUS_UNSPECIFIED);
  const [memberPhoneFilter, setMemberPhoneFilter] = useState("");
  const [bookTitleFilter, setBookTitleFilter] = useState("");
  const [borrowMember, setBorrowMember] = useState<pb.Member.AsObject | null>(null);
  const [borrowBook, setBorrowBook] = useState<pb.Book.AsObject | null>(null);
  const [memberSearch, setMemberSearch] = useState("");
  const [bookSearch, setBookSearch] = useState("");
  const [returnableLoans, setReturnableLoans] = useState<pb.Loan.AsObject[]>([]);
  const [returnLoan, setReturnLoan] = useState<pb.Loan.AsObject | null>(null);
  const [returnSearch, setReturnSearch] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const b = useBanner();

  /** Load members and books for borrow selects and phone/title loan filters. */
  const loadLookups = useCallback(async () => {
    try {
      const membersReq = new pb.ListMembersRequest();
      membersReq.setPageSize(100);
      const booksReq = new pb.ListBooksRequest();
      booksReq.setPageSize(100);
      const [membersRes, booksRes] = await Promise.all([
        client.listMembers(membersReq),
        client.listBooks(booksReq),
      ]);
      setMembers(membersRes.getMembersList().map((x) => x.toObject()));
      setBooks(booksRes.getBooksList().map((x) => x.toObject()));
    } catch (e) {
      b.setError(grpcMessage(e));
    }
  }, []); // eslint-disable-line

  /** List loans; re-runs when the status filter dropdown changes. */
  const load = useCallback(async () => {
    try {
      const req = new pb.ListLoansRequest();
      req.setPageSize(100);
      req.setStatus(filter);
      const res = await client.listLoans(req);
      setLoans(res.getLoansList().map((x) => x.toObject()));
    } catch (e) {
      b.setError(grpcMessage(e));
    }
  }, [filter]); // eslint-disable-line

  /** Open loans (outstanding + overdue) for the return picker. */
  const loadReturnableLoans = useCallback(async () => {
    try {
      const req = new pb.ListLoansRequest();
      req.setPageSize(100);
      req.setStatus(pb.LoanStatus.LOAN_STATUS_UNSPECIFIED);
      const res = await client.listLoans(req);
      setReturnableLoans(
        res
          .getLoansList()
          .map((x) => x.toObject())
          .filter((ln) => ln.status !== pb.LoanStatus.LOAN_STATUS_RETURNED),
      );
    } catch (e) {
      b.setError(grpcMessage(e));
    }
  }, []); // eslint-disable-line

  useEffect(() => {
    loadLookups();
    load();
    loadReturnableLoans();
  }, [load, loadLookups, loadReturnableLoans]);

  const memberPhoneById = useMemo(() => {
    const map = new Map<number, string>();
    for (const m of members) map.set(m.id, m.phone || "");
    return map;
  }, [members]);

  const matchesPhone = (phone: string, query: string) =>
    !query || phone.toLowerCase().includes(query.toLowerCase());

  const matchesTitle = (title: string, query: string) =>
    !query || title.toLowerCase().includes(query.toLowerCase());

  const memberMatches = useMemo(() => {
    const q = memberSearch.trim().toLowerCase();
    if (!q) return [];
    return members
      .filter(
        (m) =>
          (m.phone || "").toLowerCase().includes(q) ||
          m.name.toLowerCase().includes(q),
      )
      .slice(0, 10);
  }, [members, memberSearch]);

  const bookMatches = useMemo(() => {
    const q = bookSearch.trim().toLowerCase();
    if (!q) return [];
    return books
      .filter(
        (bk) =>
          bk.title.toLowerCase().includes(q) ||
          bk.author.toLowerCase().includes(q),
      )
      .slice(0, 10);
  }, [books, bookSearch]);

  const returnLoanMatches = useMemo(() => {
    const q = returnSearch.trim().toLowerCase();
    if (!q) return [];
    return returnableLoans
      .filter((ln) => {
        const phone = memberPhoneById.get(ln.memberId) || "";
        return (
          ln.bookTitle.toLowerCase().includes(q) ||
          ln.memberName.toLowerCase().includes(q) ||
          phone.toLowerCase().includes(q) ||
          ln.barcode.toLowerCase().includes(q) ||
          String(ln.id).includes(q)
        );
      })
      .slice(0, 10);
  }, [returnableLoans, returnSearch, memberPhoneById]);

  const visibleLoans = loans.filter((ln) => {
    if (!matchesTitle(ln.bookTitle, bookTitleFilter)) return false;
    const phone = memberPhoneById.get(ln.memberId) || "";
    return matchesPhone(phone, memberPhoneFilter);
  });

  /** Borrow any available copy of a book (server picks copy via SKIP LOCKED). */
  const borrow = async (e: React.FormEvent) => {
    e.preventDefault();
    b.show(() => {});
    if (!borrowMember || !borrowBook) return;
    setSubmitting(true);
    try {
      const req = new pb.BorrowBookRequest();
      req.setMemberId(borrowMember.id);
      req.setBookId(borrowBook.id);
      await client.borrowBook(req);
      setBorrowBook(null);
      setBorrowMember(null);
      setMemberSearch("");
      setBookSearch("");
      b.setOk("Book borrowed.");
      load();
      loadReturnableLoans();
    } catch (e) {
      b.setError(grpcMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  /** Close a loan by id; server computes any overdue fine. */
  const doReturn = async (e: React.FormEvent) => {
    e.preventDefault();
    b.show(() => {});
    if (!returnLoan) return;
    setSubmitting(true);
    try {
      const req = new pb.ReturnBookRequest();
      req.setLoanId(returnLoan.id);
      await client.returnBook(req);
      setReturnLoan(null);
      setReturnSearch("");
      b.setOk("Book returned.");
      load();
      loadReturnableLoans();
    } catch (e) {
      b.setError(grpcMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  /** Render a colored pill for outstanding / overdue / returned loans. */
  const statusPill = (s: number) => {
    if (s === pb.LoanStatus.LOAN_STATUS_RETURNED) return <span className="pill info">returned</span>;
    if (s === pb.LoanStatus.LOAN_STATUS_OVERDUE) return <span className="pill bad">overdue</span>;
    return <span className="pill warn">outstanding</span>;
  };

  /** Format protobuf Timestamp (seconds since epoch) as a locale date string. */
  const fmt = (ts?: { seconds: number }) =>
    ts ? new Date(ts.seconds * 1000).toLocaleDateString() : "—";

  return (
    <div>
      {b.error && <div className="error">{b.error}</div>}
      {b.ok && <div className="ok-banner">{b.ok}</div>}

      <div className="card">
        <h2>Borrow a book</h2>
        <form className="row" onSubmit={borrow}>
          <SearchPicker
            label="Member"
            placeholder="Search by phone or name…"
            query={memberSearch}
            onQueryChange={setMemberSearch}
            selected={borrowMember}
            onSelect={setBorrowMember}
            options={memberMatches}
            getKey={(m) => m.id}
            formatSelected={(m) => `${m.name}${m.phone ? ` · ${m.phone}` : ""}`}
            renderOption={(m) => (
              <>
                <strong>{m.name}</strong>
                <small>{m.phone || "No phone"} · {m.email}</small>
              </>
            )}
            emptyHint="No members match"
          />
          <SearchPicker
            label="Book (any available copy)"
            placeholder="Search by title or author…"
            query={bookSearch}
            onQueryChange={setBookSearch}
            selected={borrowBook}
            onSelect={setBorrowBook}
            options={bookMatches}
            getKey={(bk) => bk.id}
            formatSelected={(bk) => bk.title}
            renderOption={(bk) => (
              <>
                <strong>{bk.title}</strong>
                <small>
                  {bk.author}
                  {bk.availableCopies > 0
                    ? ` · ${bk.availableCopies} available`
                    : " · none available"}
                </small>
              </>
            )}
            emptyHint="No books match"
          />
          <button
            className="primary"
            type="submit"
            disabled={submitting || !borrowMember || !borrowBook}
          >
            Borrow
          </button>
        </form>
      </div>

      <div className="card">
        <h2>Return a book</h2>
        <form className="row" onSubmit={doReturn}>
          <SearchPicker
            label="Open loan"
            placeholder="Search by book, borrower, phone, barcode…"
            query={returnSearch}
            onQueryChange={setReturnSearch}
            selected={returnLoan}
            onSelect={setReturnLoan}
            options={returnLoanMatches}
            getKey={(ln) => ln.id}
            formatSelected={(ln) => `${ln.bookTitle} — ${ln.memberName}`}
            renderOption={(ln) => {
              const phone = memberPhoneById.get(ln.memberId) || "";
              return (
                <>
                  <strong>{ln.bookTitle}</strong>
                  <small>
                    {ln.memberName}
                    {phone ? ` · ${phone}` : ""}
                    {" · "}
                    {ln.barcode}
                    {" · due "}
                    {fmt(ln.dueAt)}
                    {ln.status === pb.LoanStatus.LOAN_STATUS_OVERDUE ? " · overdue" : ""}
                  </small>
                </>
              );
            }}
            emptyHint="No open loans match"
          />
          <button
            className="primary"
            type="submit"
            disabled={submitting || !returnLoan}
          >
            Return
          </button>
        </form>
      </div>

      <div className="card">
        <h2>Loans</h2>
        <div className="row" style={{ marginBottom: 12 }}>
          <label>
            Status
            <select value={filter} onChange={(e) => setFilter(Number(e.target.value))}>
              <option value={pb.LoanStatus.LOAN_STATUS_UNSPECIFIED}>All</option>
              <option value={pb.LoanStatus.LOAN_STATUS_OUTSTANDING}>Outstanding</option>
              <option value={pb.LoanStatus.LOAN_STATUS_OVERDUE}>Overdue</option>
              <option value={pb.LoanStatus.LOAN_STATUS_RETURNED}>Returned</option>
            </select>
          </label>
          <label>
            Member
            <input
              placeholder="Phone…"
              value={memberPhoneFilter}
              onChange={(e) => setMemberPhoneFilter(e.target.value)}
            />
          </label>
          <label>
            Book
            <input
              placeholder="Title…"
              value={bookTitleFilter}
              onChange={(e) => setBookTitleFilter(e.target.value)}
            />
          </label>
        </div>
        <table>
          <thead>
            <tr>
              <th>Loan</th>
              <th>Book</th>
              <th>Barcode</th>
              <th>Member</th>
              <th>Borrowed</th>
              <th>Due</th>
              <th>Returned</th>
              <th>Fine</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {visibleLoans.map((ln) => (
              <tr key={ln.id}>
                <td>{ln.id}</td>
                <td>{ln.bookTitle}</td>
                <td>{ln.barcode}</td>
                <td>{ln.memberName}</td>
                <td>{fmt(ln.borrowedAt)}</td>
                <td>{fmt(ln.dueAt)}</td>
                <td>{fmt(ln.returnedAt)}</td>
                <td>{ln.fineCents ? `$${(ln.fineCents / 100).toFixed(2)}` : "—"}</td>
                <td>{statusPill(ln.status)}</td>
              </tr>
            ))}
            {visibleLoans.length === 0 && (
              <tr>
                <td colSpan={9} className="muted">
                  {loans.length === 0 ? "No loans." : "No loans match the filters."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
