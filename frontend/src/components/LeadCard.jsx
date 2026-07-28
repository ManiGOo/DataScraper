import React from 'react';

const LeadCard = ({ lead }) => {
  return (
    <div className="bg-slate-800/40 border border-slate-700/50 rounded-xl p-5 hover:border-brand-500/50 transition-colors group h-full flex flex-col">
      <div className="flex justify-between items-start mb-3 gap-2">
        <h4 className="font-bold text-white text-lg group-hover:text-brand-400 transition-colors line-clamp-2 break-all">{lead.name}</h4>
        <span className="bg-brand-900/50 text-brand-400 text-[10px] font-bold px-2 py-1 rounded border border-brand-500/20 shrink-0">SME</span>
      </div>
      <div className="space-y-2 text-xs text-slate-400 flex-1">
        <div className="flex items-center gap-2"><span className="text-slate-500 w-4">🌐</span> {lead.domain}</div>
        <div className="flex items-center gap-2"><span className="text-slate-500 w-4">📍</span> {lead.region || 'Unknown Region'}</div>
        <div className="flex items-center gap-2"><span className="text-slate-500 w-4">📁</span> {lead.source_directory || lead.source || 'Search Directory'}</div>
        <div className="flex items-center gap-2"><span className="text-slate-500 w-4">💰</span> {lead.estimated_revenue || 'Unknown Rev'}</div>
      </div>
      
      {/* Contacts Section */}
      {lead.contacts && lead.contacts.length > 0 ? (
        <div className="mt-4 pt-4 border-t border-slate-700/50 space-y-3">
          {lead.contacts.map((contact, j) => (
            <div key={j} className="text-xs">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-semibold text-slate-200">{contact.name}</span>
                <span className="text-slate-500 text-[10px]">({contact.title})</span>
                {contact.linkedin_url && (
                  <a href={contact.linkedin_url} target="_blank" rel="noreferrer" className="text-blue-400 hover:text-blue-300 ml-auto" title="LinkedIn Profile">
                    🔗
                  </a>
                )}
              </div>
              {contact.email && (
                <div className="flex items-center gap-2 text-slate-400 mt-1">
                  <span className="text-slate-500 w-3">✉️</span> 
                  <a href={`mailto:${contact.email}`} className="hover:text-brand-400 transition-colors">{contact.email}</a>
                </div>
              )}
              {contact.phone && (
                <div className="flex items-center gap-2 text-slate-400 mt-1">
                  <span className="text-slate-500 w-3">📞</span> 
                  <a href={`tel:${contact.phone}`} className="hover:text-brand-400 transition-colors">{contact.phone}</a>
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 pt-4 border-t border-slate-700/50">
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-xs py-2 px-3 rounded flex items-center justify-center">
            No valid contacts or emails found on website
          </div>
        </div>
      )}
    </div>
  );
};

export default LeadCard;
