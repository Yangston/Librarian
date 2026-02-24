export default function DatabasePage() {
  return (
    <main className="grid two">
      <section className="panel">
        <h2>/database</h2>
        <p>
          This view is intended to query extracted entities, facts, and relations by conversation.
        </p>
        <ul className="list">
          <li>GET `/entities` for entity inventory</li>
          <li>GET `/facts` for normalized claims</li>
          <li>GET `/relations` for entity-to-entity links</li>
        </ul>
      </section>
      <section className="panel">
        <h2>Traceability</h2>
        <p>
          Facts and relations include source message IDs. Use those IDs to render explainability
          links and message context.
        </p>
      </section>
    </main>
  );
}

