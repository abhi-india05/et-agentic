import React, { useState } from 'react';
import { Send, Copy, CheckCheck, Sparkles, Building2, Briefcase, FileText, Bot } from 'lucide-react';
import AgentFlowVisualizer from '../components/AgentFlowVisualizer';

const OutreachPage = () => {
  const [formData, setFormData] = useState({
    company: '',
    industry: '',
    notes: '',
  });

  const [isActive, setIsActive] = useState(false);
  const [agentOutputs, setAgentOutputs] = useState({});
  const [emails, setEmails] = useState(null);
  const [copiedIndex, setCopiedIndex] = useState(null);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleCopy = (text, index) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const generateMockFlow = async () => {
    setIsActive(true);
    setAgentOutputs({});
    setEmails(null);

    const steps = [
      {
        id: 'Prospecting',
        data: { status: 'success', confidence: 0.92, reasoning: 'Identified 3 key decision makers at TargetCo matching ICP.' }
      },
      {
        id: 'Digital Twin',
        data: { status: 'success', confidence: 0.88, reasoning: 'Simulated 50 cold call scenarios. Objection handling optimized for QA.' }
      },
      {
        id: 'Outreach',
        data: { status: 'success', confidence: 0.95, reasoning: 'Drafted hyper-personalized sequences using Challenger Sale framework.' }
      },
      {
        id: 'Action',
        data: { status: 'success', confidence: 0.99, reasoning: 'Approved and ready for deployment via integration layer.' }
      }
    ];

    let currentOutputs = {};
    for (const step of steps) {
      await new Promise(r => setTimeout(r, 1500));
      currentOutputs = { ...currentOutputs, [step.id]: step.data };
      setAgentOutputs(currentOutputs);
    }

    setTimeout(() => {
      setIsActive(false);
      setEmails([
        {
          subject: 'Question about your pipeline velocity at ' + (formData.company || 'your company'),
          body: `Hi there,\n\nNoticed that top performers in ${formData.industry || 'your space'} are shifting to autonomous workflows. Our AI agents can take over the top-of-funnel entirely.\n\nWorth a chat next Tuesday?`
        },
        {
          subject: 'Re: Question about your pipeline velocity',
          body: `Following up here. Are you currently exploring ways to automate your outbound? We just helped a similar company 3x their meeting booked rate.\n\nLet me know if you want the case study.`
        },
        {
          subject: 'Last attempt - Autonomous Sales',
          body: `I'll close the file on this for now. If you ever want to scale your outreach without adding headcount, RevOps AI is here.\n\nBest,`
        }
      ]);
    }, 1000);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.company) return;
    generateMockFlow();
  };

  return (
    <div className="min-h-screen bg-void text-text p-6 lg:p-10 font-body">
      <div className="max-w-7xl mx-auto space-y-8">
        
        <header className="mb-10">
          <h1 className="text-4xl font-display font-bold text-transparent bg-clip-text bg-gradient-to-r from-accent to-plasma inline-flex items-center gap-3">
            <Sparkles className="w-8 h-8 text-accent" />
            Autonomous Outreach
          </h1>
          <p className="text-text-dim mt-2 text-lg">Deploy agents to research, draft, and optimize sales sequences.</p>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          
          {/* LEFT: FORM */}
          <div className="lg:col-span-4 bg-surface rounded-2xl border border-border p-6 shadow-glow-accent/5 sticky top-10">
            <h2 className="text-xl font-display font-semibold mb-6 flex items-center gap-2">
              Target Parameters
            </h2>
            
            <form onSubmit={handleSubmit} className="space-y-5">
              <div className="space-y-2">
                <label className="text-sm font-medium text-text-dim flex items-center gap-2">
                  <Building2 className="w-4 h-4" /> Company Name
                </label>
                <input 
                  type="text" 
                  name="company"
                  value={formData.company}
                  onChange={handleInputChange}
                  className="w-full bg-panel border border-border rounded-lg px-4 py-3 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-all text-text"
                  placeholder="e.g. Acme Corp"
                  required
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-text-dim flex items-center gap-2">
                  <Briefcase className="w-4 h-4" /> Industry
                </label>
                <input 
                  type="text" 
                  name="industry"
                  value={formData.industry}
                  onChange={handleInputChange}
                  className="w-full bg-panel border border-border rounded-lg px-4 py-3 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-all text-text"
                  placeholder="e.g. SaaS"
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-text-dim flex items-center gap-2">
                  <FileText className="w-4 h-4" /> Context / Notes
                </label>
                <textarea 
                  name="notes"
                  value={formData.notes}
                  onChange={handleInputChange}
                  rows="4"
                  className="w-full bg-panel border border-border rounded-lg px-4 py-3 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-all text-text resize-none"
                  placeholder="Specific value propositions, pain points, etc."
                ></textarea>
              </div>

              <button 
                type="submit" 
                disabled={isActive || !formData.company}
                className="w-full bg-plasma hover:bg-plasma/90 text-white font-medium rounded-lg px-4 py-3 mt-4 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shadow-glow-accent"
              >
                {isActive ? (
                  <>Deploying Agents...</>
                ) : (
                  <>
                    <Send className="w-5 h-5" /> Execute Campaign
                  </>
                )}
              </button>
            </form>
          </div>

          {/* RIGHT: OUTPUT AREA */}
          <div className="lg:col-span-8 space-y-8">
            {/* Agent Visualization */}
            {(isActive || Object.keys(agentOutputs).length > 0) && (
              <div className="animate-fade-up">
                <AgentFlowVisualizer isActive={isActive} agentOutputs={agentOutputs} />
              </div>
            )}

            {/* Generated Sequence Results */}
            {emails && !isActive && (
              <div className="animate-slide-in space-y-6">
                <h3 className="text-2xl font-display font-semibold text-text flex items-center gap-2">
                  <span className="w-2 h-8 bg-success rounded-full"></span>
                  Generated Sequence
                </h3>
                
                <div className="grid gap-4">
                  {emails.map((email, i) => (
                    <div key={i} className="bg-surface rounded-xl border border-border p-6 hover:border-success/30 transition-colors group relative">
                      <div className="absolute top-6 right-6 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button 
                          onClick={() => handleCopy(email.body, i)}
                          className="bg-panel hover:bg-border text-text p-2 rounded-md border border-border flex items-center gap-2 text-sm transition-colors"
                        >
                          {copiedIndex === i ? <CheckCheck className="w-4 h-4 text-success" /> : <Copy className="w-4 h-4" />}
                          {copiedIndex === i ? 'Copied' : 'Copy'}
                        </button>
                      </div>
                      
                      <div className="mb-4 pr-24">
                        <span className="text-xs font-mono text-accent bg-void px-2 py-1 rounded border border-border mb-2 inline-block">
                          Step {i + 1}
                        </span>
                        <h4 className="font-medium text-text mt-1">Subject: {email.subject}</h4>
                      </div>
                      
                      <div className="bg-void rounded-lg p-4 font-mono text-sm text-text-dim border border-border whitespace-pre-wrap">
                        {email.body}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {!isActive && Object.keys(agentOutputs).length === 0 && !emails && (
              <div className="h-full min-h-[400px] border-2 border-dashed border-border rounded-2xl flex flex-col items-center justify-center text-text-dim bg-panel/30">
                <Bot className="w-16 h-16 mb-4 opacity-50" />
                <p className="text-lg">Awaiting campaign parameters.</p>
                <p className="text-sm mt-2 max-w-sm text-center">Fill out the form on the left to deploy the autonomous sales team.</p>
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  );
};

export default OutreachPage;
