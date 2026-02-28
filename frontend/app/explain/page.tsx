import Link from "next/link";

export default function ExplainLandingPage() {
  return (
    <section className="panel">
      <h2>Explainability</h2>
      <p className="subtle">
        Open a specific fact or relation explain page from entity tables, search results, or direct URL.
      </p>
      <p>
        Examples: <code>/explain/facts/1</code> and <code>/explain/relations/1</code>.
      </p>
      <p>
        <Link href="/search">Go to search</Link>
      </p>
    </section>
  );
}

