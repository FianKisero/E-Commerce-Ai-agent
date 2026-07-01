import { useEffect, useState } from 'react';

type EventItem = {
  type: string;
  message?: string;
  product?: {
    name: string;
    price: string;
    merchant: string;
    compliance: string[];
    link: string;
  };
  actions?: string[];
};

export default function App() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('ws://127.0.0.1:8000/ws');

    ws.onopen = () => {
      setConnected(true);
      ws.send(JSON.stringify({ query: 'laptop for remote teams' }));
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data) as EventItem;
      setEvents((prev) => [...prev, data]);
    };
    ws.onclose = () => setConnected(false);

    return () => ws.close();
  }, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-8">
        <header className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-2xl shadow-black/20">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.3em] text-emerald-400">MCP Autonomous Agent Terminal</p>
              <h1 className="mt-2 text-3xl font-semibold">E-Commerce Procurement Agent</h1>
            </div>
            <div className={`rounded-full px-3 py-1 text-sm ${connected ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-800 text-slate-400'}`}>
              {connected ? 'Live' : 'Connecting'}
            </div>
          </div>
        </header>

        <main className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <section className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">
            <h2 className="text-xl font-semibold">Activity Stream</h2>
            <div className="mt-4 space-y-3">
              {events.map((event, index) => (
                <div key={index} className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
                  {event.type === 'thought' && <p className="text-slate-300">{event.message}</p>}
                  {event.type === 'product' && event.product && (
                    <div>
                      <p className="text-lg font-semibold text-emerald-300">{event.product.name}</p>
                      <p className="mt-1 text-slate-300">Price: {event.product.price}</p>
                      <p className="text-slate-300">Merchant: {event.product.merchant}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {event.product.compliance.map((item) => (
                          <span key={item} className="rounded-full bg-emerald-500/15 px-3 py-1 text-sm text-emerald-300">
                            {item}
                          </span>
                        ))}
                      </div>
                      <a href={event.product.link} target="_blank" rel="noreferrer" className="mt-3 inline-block text-blue-400">
                        Verify on Site
                      </a>
                    </div>
                  )}
                  {event.type === 'interrupt' && (
                    <div>
                      <p className="text-amber-300">{event.message}</p>
                      <div className="mt-3 flex gap-3">
                        {event.actions?.map((action) => (
                          <button key={action} className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-slate-950">
                            {action}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>

          <aside className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6">
            <h2 className="text-xl font-semibold">Transaction Gate</h2>
            <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/70 p-4">
              <p className="text-sm text-slate-400">When the agent reaches the human approval checkpoint, this panel will become the primary action surface.</p>
              <div className="mt-4 rounded-xl border border-amber-500/40 bg-amber-500/10 p-4 text-amber-200">
                <p className="font-medium">Approval required</p>
                <p className="mt-1 text-sm">The workflow pauses here until you confirm or cancel.</p>
              </div>
            </div>
          </aside>
        </main>
      </div>
    </div>
  );
}
