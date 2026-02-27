export default function HomePage() {
  return (
    <main className="grid">
      <section className="panel heroPanel">
        <h2>Phase 2 Testing Console</h2>
        <p>
          Librarian now supports two testing modes: batch JSON ingestion and live GPT chat turns
          that can auto-run extraction and continuously update the structured memory view.
        </p>
        <p>
          Use <code>/conversation</code> for the unified console, <code>/live</code> for focused
          chat testing, and <code>/database</code> / <code>/explain</code> for inspection.
        </p>
        <div className="grid two">
          <div className="panel inset">
            <h3 className="subhead">Testing Mode 1: JSON Batch</h3>
            <ol className="list">
              <li>Paste or edit a message batch payload</li>
              <li>POST messages</li>
              <li>Run extraction</li>
              <li>Inspect structured rows and explainability</li>
            </ol>
          </div>
          <div className="panel inset">
            <h3 className="subhead">Testing Mode 2: Live Chat</h3>
            <ol className="list">
              <li>Send a live prompt to GPT</li>
              <li>Persist user + assistant messages automatically</li>
              <li>Optionally auto-run extraction per turn</li>
              <li>Watch entities/facts/relations update live</li>
            </ol>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>Core Routes</h2>
        <div className="code mono">
          <div>POST /conversations/:id/messages</div>
          <div>POST /conversations/:id/chat/turn</div>
          <div>GET /conversations/:id/messages</div>
          <div>POST /conversations/:id/extract</div>
          <div>GET /conversations/:id/entities</div>
          <div>GET /conversations/:id/entity-merges</div>
          <div>GET /conversations/:id/resolution-events</div>
          <div>GET /conversations/:id/facts</div>
          <div>GET /conversations/:id/relations</div>
          <div>GET /search?q=...&conversation_id=...</div>
          <div>GET /conversations/:id/summary</div>
          <div>GET /entities/:id/graph</div>
          <div>GET /entities/:id/timeline</div>
          <div>GET /conversations/:id/facts/:factId/explain</div>
          <div>GET /conversations/:id/relations/:relationId/explain</div>
          <div>GET /facts/:factId/explain</div>
          <div>GET /relations/:relationId/explain</div>
        </div>
      </section>
    </main>
  );
}
