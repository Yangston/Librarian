export default function HomePage() {
  return (
    <main className="grid two">
      <section className="panel">
        <h2>Phase 1 Goal</h2>
        <p>
          Prove a deterministic pipeline from conversation messages into a transparent relational
          database.
        </p>
        <ol className="list">
          <li>Ingest messages</li>
          <li>Run extraction</li>
          <li>Inspect entities, facts, and relations</li>
          <li>Trace records back to source messages</li>
        </ol>
      </section>
      <section className="panel">
        <h2>Backend Routes</h2>
        <div className="code mono">
          <div>POST /conversations/:id/messages</div>
          <div>GET /conversations/:id/messages</div>
          <div>POST /conversations/:id/extract</div>
          <div>GET /conversations/:id/entities</div>
          <div>GET /conversations/:id/facts</div>
          <div>GET /conversations/:id/relations</div>
          <div>GET /conversations/:id/facts/:factId/explain</div>
          <div>GET /conversations/:id/relations/:relationId/explain</div>
        </div>
      </section>
    </main>
  );
}

