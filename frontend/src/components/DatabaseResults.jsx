import React, { useState, useEffect, useMemo } from 'react';
import LeadCard from './LeadCard';

const DatabaseResults = () => {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchDatabase = async () => {
      try {
        const res = await fetch('/api/sdr/records?limit=5000');
        if (!res.ok) throw new Error('Failed to fetch database records');
        const data = await res.json();
        setLeads(data.leads || []);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchDatabase();
  }, []);

  // Group by region and source_directory
  const groupedLeads = useMemo(() => {
    const groups = {};
    leads.forEach(lead => {
      const region = lead.region || 'Global/Unknown';
      const source = lead.source_directory || lead.source || 'Search Directory';
      const key = `${region} — ${source}`;
      
      if (!groups[key]) groups[key] = [];
      groups[key].push(lead);
    });
    return groups;
  }, [leads]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-4 border-slate-700 border-t-brand-500 rounded-full"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center text-red-400">
        Error loading database: {error}
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-8 max-w-[1400px] mx-auto w-full">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h2 className="text-2xl font-bold text-white mb-2">Database Overview</h2>
          <p className="text-slate-400">Total SMEs Extracted: {leads.length}</p>
        </div>
      </div>

      {Object.keys(groupedLeads).length === 0 ? (
        <div className="py-12 text-center text-slate-500 border border-dashed border-slate-700 rounded-xl">
          No records found in the database. Run a campaign first!
        </div>
      ) : (
        <div className="space-y-12">
          {Object.entries(groupedLeads).map(([groupKey, groupLeads]) => (
            <div key={groupKey}>
              <div className="flex items-center gap-4 mb-4 border-b border-slate-700/50 pb-2">
                <h3 className="text-lg font-bold text-slate-200">{groupKey}</h3>
                <span className="bg-slate-800 text-slate-400 text-xs px-2 py-1 rounded-full">{groupLeads.length} leads</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                {groupLeads.map(lead => (
                  <LeadCard key={lead.id} lead={lead} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DatabaseResults;
