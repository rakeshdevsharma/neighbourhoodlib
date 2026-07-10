"use client";

/**
 * Main library admin UI — a tabbed single page that talks to the backend via
 * gRPC-Web (through Envoy). Each tab is a self-contained section with its own
 * forms, list view, and success/error banners.
 */
import { useCallback, useEffect, useState } from "react";
import { client, grpcMessage, pb } from "@/lib/client";

type Tab = "books" | "members" | "loans";

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
  const show = (fn: () => void) => {
    setError("");
    setOk("");
    fn();
  };
  return { error, ok, setError, setOk, show };
}

// --------------------------------------------------------------------------- //
// Books — catalog titles, add copies, list availability
// --------------------------------------------------------------------------- //
function BooksSection() {
  const [books, setBooks] = useState<pb.Book.AsObject[]>([]);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [isbn, setIsbn] = useState("");
  const [copyBookId, setCopyBookId] = useState<number | null>(null);
  const [barcode, setBarcode] = useState("");
  const [shelf, setShelf] = useState("");
  const b = useBanner();

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

  const createBook = async (e: React.FormEvent) => {
    e.preventDefault();
    b.show(() => {});
    try {
      const req = new pb.CreateBookRequest();
      req.setTitle(title);
      req.setAuthor(author);
      req.setIsbn(isbn);
      await client.createBook(req);
      setTitle("");
      setAuthor("");
      setIsbn("");
      b.setOk("Book created.");
      load();
    } catch (e) {
      b.setError(grpcMessage(e));
    }
  };

  const addCopy = async (e: React.FormEvent) => {
    e.preventDefault();
    b.show(() => {});
    if (!copyBookId) return;
    try {
      const req = new pb.AddCopyRequest();
      req.setBookId(copyBookId);
      req.setBarcode(barcode);
      req.setCondition(pb.CopyCondition.COPY_CONDITION_GOOD);
      req.setShelfLocation(shelf);
      await client.addCopy(req);
      setBarcode("");
      setShelf("");
      b.setOk("Copy added.");
      load();
    } catch (e) {
      b.setError(grpcMessage(e));
    }
  };

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
          <button className="primary" type="submit">Create</button>
        </form>
      </div>

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
          <button className="primary" type="submit">Add copy</button>
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
              </tr>
            ))}
            {books.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">No books yet.</td>
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
function MembersSection() {
  const [members, setMembers] = useState<pb.Member.AsObject[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const b = useBanner();

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

  const createMember = async (e: React.FormEvent) => {
    e.preventDefault();
    b.show(() => {});
    try {
      const req = new pb.CreateMemberRequest();
      req.setName(name);
      req.setEmail(email);
      req.setPhone(phone);
      await client.createMember(req);
      setName("");
      setEmail("");
      setPhone("");
      b.setOk("Member created.");
      load();
    } catch (e) {
      b.setError(grpcMessage(e));
    }
  };

  const statusLabel = (s: number) =>
    s === pb.MemberStatus.MEMBER_STATUS_ACTIVE ? "active" : "suspended";

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
          <button className="primary" type="submit">Create</button>
        </form>
      </div>

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
              </tr>
            ))}
            {members.length === 0 && (
              <tr>
                <td colSpan={5} className="muted">No members yet.</td>
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
function LoansSection() {
  const [loans, setLoans] = useState<pb.Loan.AsObject[]>([]);
  const [filter, setFilter] = useState<number>(pb.LoanStatus.LOAN_STATUS_UNSPECIFIED);
  const [memberId, setMemberId] = useState("");
  const [bookId, setBookId] = useState("");
  const [loanId, setLoanId] = useState("");
  const b = useBanner();

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

  useEffect(() => {
    load();
  }, [load]);

  const borrow = async (e: React.FormEvent) => {
    e.preventDefault();
    b.show(() => {});
    try {
      const req = new pb.BorrowBookRequest();
      req.setMemberId(Number(memberId));
      req.setBookId(Number(bookId));
      await client.borrowBook(req);
      setBookId("");
      b.setOk("Book borrowed.");
      load();
    } catch (e) {
      b.setError(grpcMessage(e));
    }
  };

  const doReturn = async (e: React.FormEvent) => {
    e.preventDefault();
    b.show(() => {});
    try {
      const req = new pb.ReturnBookRequest();
      req.setLoanId(Number(loanId));
      await client.returnBook(req);
      setLoanId("");
      b.setOk("Book returned.");
      load();
    } catch (e) {
      b.setError(grpcMessage(e));
    }
  };

  const statusPill = (s: number) => {
    if (s === pb.LoanStatus.LOAN_STATUS_RETURNED) return <span className="pill info">returned</span>;
    if (s === pb.LoanStatus.LOAN_STATUS_OVERDUE) return <span className="pill bad">overdue</span>;
    return <span className="pill warn">outstanding</span>;
  };

  const fmt = (ts?: { seconds: number }) =>
    ts ? new Date(ts.seconds * 1000).toLocaleDateString() : "—";

  return (
    <div>
      {b.error && <div className="error">{b.error}</div>}
      {b.ok && <div className="ok-banner">{b.ok}</div>}

      <div className="card">
        <h2>Borrow a book</h2>
        <form className="row" onSubmit={borrow}>
          <label>
            Member ID
            <input value={memberId} onChange={(e) => setMemberId(e.target.value)} required />
          </label>
          <label>
            Book ID (any available copy)
            <input value={bookId} onChange={(e) => setBookId(e.target.value)} required />
          </label>
          <button className="primary" type="submit">Borrow</button>
        </form>
      </div>

      <div className="card">
        <h2>Return a book</h2>
        <form className="row" onSubmit={doReturn}>
          <label>
            Loan ID
            <input value={loanId} onChange={(e) => setLoanId(e.target.value)} required />
          </label>
          <button className="primary" type="submit">Return</button>
        </form>
      </div>

      <div className="card">
        <h2>Loans</h2>
        <div className="row" style={{ marginBottom: 12 }}>
          <label>
            Filter
            <select value={filter} onChange={(e) => setFilter(Number(e.target.value))}>
              <option value={pb.LoanStatus.LOAN_STATUS_UNSPECIFIED}>All</option>
              <option value={pb.LoanStatus.LOAN_STATUS_OUTSTANDING}>Outstanding</option>
              <option value={pb.LoanStatus.LOAN_STATUS_OVERDUE}>Overdue</option>
              <option value={pb.LoanStatus.LOAN_STATUS_RETURNED}>Returned</option>
            </select>
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
            {loans.map((ln) => (
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
            {loans.length === 0 && (
              <tr>
                <td colSpan={9} className="muted">No loans.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
