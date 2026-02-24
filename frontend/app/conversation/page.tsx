export default function ConversationPage() {
  return (
    <main className="grid">
      <section className="panel">
        <h2>/conversation</h2>
        <p>
          Use this page to paste or compose a conversation payload and send it to the backend
          ingestion endpoint.
        </p>
        <div className="code mono">
          {`POST /conversations/market-digest/messages
{
  "messages": [
    { "role": "user", "content": "AAPL was up 3.2% today." },
    { "role": "assistant", "content": "TSLA reported quarterly deliveries." }
  ]
}`}
        </div>
      </section>
    </main>
  );
}

