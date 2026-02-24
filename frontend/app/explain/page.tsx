export default function ExplainPage() {
  return (
    <main className="grid">
      <section className="panel">
        <h2>/explain</h2>
        <p>
          This page is reserved for record-level traceability. Query a fact or relation explain
          endpoint and display source messages with exact snippets.
        </p>
        <div className="code mono">
          <div>GET /conversations/market-digest/facts/1/explain</div>
          <div>GET /conversations/market-digest/relations/1/explain</div>
        </div>
      </section>
    </main>
  );
}

