import React, { useState } from 'react';
import LeadCard from './LeadCard';

const DiscoveryTerminal = () => {
  const [region, setRegion] = useState('India (IndiaMart SME)');
  const [sector, setSector] = useState('Pharmaceutical Formulations');
  const [maxRecords, setMaxRecords] = useState(5);
  const [status, setStatus] = useState('idle');
  const [logs, setLogs] = useState([]);
  const [leads, setLeads] = useState([]);

  const startCampaign = async () => {
    setStatus('running');
    setLogs(prev => [...prev, `[System] Starting SME Discovery for ${region} - ${sector} (Max: ${maxRecords})`]);
    setLeads([]);
    
    try {
      const res = await fetch('/api/sdr/campaigns/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_region: region, target_sector: sector, max_results: maxRecords })
      });
      const data = await res.json();
      
      if(data.campaign_id) {
        pollStatus(data.campaign_id);
      }
    } catch (e) {
      setStatus('error');
      setLogs(prev => [...prev, `[Error] ${e.message}`]);
    }
  };

  const pollStatus = async (id) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/sdr/campaigns/status/${id}`);
        const data = await res.json();
        
        setLogs(prev => [...prev, `[Polled] Status: ${data.status}`]);
        
        if (data.status === 'COMPLETED' || data.status === 'ERROR') {
          clearInterval(interval);
          setStatus(data.status.toLowerCase());
          if (data.leads) setLeads(data.leads);
        }
      } catch(e) {
        // ignore fetch errors
      }
    }, 2000);
  };

  return (
    <div className="flex h-full w-full">
      {/* Sidebar Configurations */}
      <aside className="w-80 bg-dark-800 border-r border-slate-700/50 flex flex-col shadow-2xl z-10 shrink-0">
        <div className="p-6 border-b border-slate-700/50">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wide">Campaign Settings</h2>
        </div>
        
        <div className="p-6 flex-1 flex flex-col gap-5 overflow-y-auto">
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">Target Region / Directory</label>
            <select 
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 text-sm focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-all text-white"
            >
              <optgroup label="India">
                <option value="India (IndiaMart SME)">IndiaMart (FDF/API)</option>
                <option value="India (Maps)">Google Maps (India)</option>
              </optgroup>
              <optgroup label="Middle East">
                <option value="UAE Maps">UAE (Google Maps)</option>
                <option value="Israel Maps">Israel (Google Maps)</option>
                <option value="Oman Maps">Oman (Google Maps)</option>
              </optgroup>
              <optgroup label="Europe">
                <option value="EU Directory (Germany)">Germany (SME Directory)</option>
                <option value="EU Directory (UK)">UK (SME Directory)</option>
              </optgroup>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">Industry Sector</label>
            <input 
              type="text" 
              value={sector}
              onChange={(e) => setSector(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 text-sm focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-all text-white"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">Max Data Records</label>
            <select 
              value={maxRecords}
              onChange={(e) => setMaxRecords(Number(e.target.value))}
              className="w-full bg-slate-800 border border-slate-700 rounded-md py-2 px-3 text-sm focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 transition-all text-white"
            >
              <option value={5}>5 Records (Testing)</option>
              <option value={20}>20 Records</option>
              <option value={100}>100 Records</option>
              <option value={500}>500 Records</option>
              <option value={1000}>1,000 Records</option>
              <option value={5000}>5,000 Records (Scale)</option>
            </select>
            <p className="text-[10px] text-slate-500 mt-1">Larger limits will take significantly longer to deep-scrape and verify contacts.</p>
          </div>
        </div>

        <div className="p-6 border-t border-slate-700/50">
          <button 
            onClick={startCampaign}
            disabled={status === 'running'}
            className="w-full bg-brand-600 hover:bg-brand-500 text-white font-bold py-3 px-4 rounded-md transition-all disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {status === 'running' ? (
              <><span className="animate-spin w-4 h-4 border-2 border-white/20 border-t-white rounded-full"></span> Running Discovery</>
            ) : (
              'Launch Discovery'
            )}
          </button>
        </div>
      </aside>

      {/* Main Panel */}
      <main className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <div className="p-8 max-w-7xl mx-auto w-full space-y-8">
          
          {/* Terminal Console */}
          <div className="bg-[#0D1117] border border-slate-700/50 rounded-xl overflow-hidden shadow-xl h-64 flex flex-col">
            <div className="bg-[#161B22] border-b border-slate-700/50 px-4 py-2 flex items-center">
              <div className="flex gap-2">
                <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
                <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
                <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
              </div>
              <span className="text-xs font-mono text-slate-400 ml-2">Live Progress Terminal</span>
            </div>
            <div className="p-4 overflow-y-auto font-mono text-xs text-green-400 leading-relaxed flex-1 flex flex-col gap-1">
              {logs.length === 0 ? (
                <span className="text-slate-500">Ready to start discovery...</span>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="whitespace-pre-wrap">{log}</div>
                ))
              )}
            </div>
          </div>

          {/* Results Grid */}
          <div>
             <h3 className="text-sm font-semibold text-slate-300 mb-4 uppercase tracking-wide">Discovered SMEs ({leads.length})</h3>
             <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                {leads.length === 0 && status !== 'running' && (
                  <div className="col-span-full py-12 text-center text-slate-500 border border-dashed border-slate-700 rounded-xl">
                    No leads discovered yet. Start a campaign to find local SMEs.
                  </div>
                )}
                {leads.map((lead, i) => (
                  <LeadCard key={i} lead={lead} />
                ))}
             </div>
          </div>

        </div>
      </main>
    </div>
  );
};

export default DiscoveryTerminal;
