import { useState } from 'react';
import DiscoveryTerminal from './components/DiscoveryTerminal';
import DatabaseResults from './components/DatabaseResults';

function App() {
  const [activeTab, setActiveTab] = useState('discovery');
  
  return (
    <div className="flex flex-col h-screen bg-dark-900 font-sans text-slate-300">
      {/* Top Navbar */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-slate-700/50 bg-dark-800 shrink-0 shadow-sm z-20">
        <div className="flex items-center gap-8">
          <h1 className="text-xl font-bold text-white flex items-center gap-2">
            <span className="text-brand-500">❖</span> AI SDR Copilot
          </h1>
          <nav className="flex gap-2">
            <button 
              onClick={() => setActiveTab('discovery')}
              className={`px-4 py-2 rounded-md font-semibold text-sm transition-colors ${activeTab === 'discovery' ? 'bg-brand-500/20 text-brand-400' : 'hover:bg-slate-800 text-slate-400'}`}
            >
              Discovery Terminal
            </button>
            <button 
              onClick={() => setActiveTab('results')}
              className={`px-4 py-2 rounded-md font-semibold text-sm transition-colors ${activeTab === 'results' ? 'bg-brand-500/20 text-brand-400' : 'hover:bg-slate-800 text-slate-400'}`}
            >
              Database Results
            </button>
          </nav>
        </div>
      </header>
      
      {/* Main Content Area */}
      <main className="flex-1 overflow-hidden flex">
        {activeTab === 'discovery' ? <DiscoveryTerminal /> : <DatabaseResults />}
      </main>
    </div>
  );
}

export default App;
