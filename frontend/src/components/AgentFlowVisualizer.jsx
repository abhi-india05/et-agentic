import React from 'react';
import { CheckCircle2, XCircle, Loader2, Bot, Circle, ChevronRight } from 'lucide-react';

const AgentFlowVisualizer = ({ agentOutputs, isActive }) => {
  // Ordered agent flow based on standard AI outreach steps
  const agentSteps = [
    { id: 'Prospecting', label: 'Prospecting Agent' },
    { id: 'Digital Twin', label: 'Digital Twin Agent' },
    { id: 'Outreach', label: 'Outreach Agent' },
    { id: 'Action', label: 'Action Agent' },
  ];

  return (
    <div className="w-full bg-surface rounded-xl p-6 border border-border shadow-glow-accent/5 max-w-2xl mx-auto">
      <h3 className="text-xl font-display font-semibold text-text mb-6 flex items-center gap-2">
        <Bot className="w-6 h-6 text-plasma" />
        Agent Operations Flow
      </h3>

      <div className="relative">
        <div className="absolute left-6 top-0 bottom-0 w-px bg-border z-0"></div>

        <div className="space-y-6 relative z-10">
          {agentSteps.map((step, index) => {
            const output = agentOutputs[step.id];
            
            // Determine status
            let status = 'pending';
            if (output?.status === 'success') status = 'success';
            if (output?.status === 'failed' || output?.status === 'error') status = 'error';
            if (isActive && !output && status !== 'success' && status !== 'error' ) {
              // Simple heuristic: if preceding is success, this is running (or it's the first one)
              const previousOutput = index > 0 ? agentOutputs[agentSteps[index - 1].id] : null;
              if (index === 0 || previousOutput?.status === 'success') {
                status = 'running';
              }
            }

            return (
              <div key={step.id} className="flex items-start gap-4">
                <div className="mt-1 bg-surface p-1 rounded-full z-10">
                  {status === 'success' && <CheckCircle2 className="w-6 h-6 text-success" />}
                  {status === 'error' && <XCircle className="w-6 h-6 text-danger" />}
                  {status === 'running' && <Loader2 className="w-6 h-6 text-accent animate-spin" />}
                  {status === 'pending' && <Circle className="w-6 h-6 text-muted" />}
                </div>

                <div 
                  className={`flex-1 rounded-lg border p-4 transition-all duration-300 ${
                    status === 'running' ? 'border-accent shadow-glow-accent bg-panel' : 
                    status === 'success' ? 'border-success/30 bg-panel' :
                    status === 'error' ? 'border-danger/30 bg-panel shadow-glow-danger' :
                    'border-border bg-surface opacity-50'
                  }`}
                >
                  <div className="flex justify-between items-center mb-2">
                    <h4 className={`font-mono font-medium ${
                      status === 'running' || status === 'success' ? 'text-plasma' : 'text-text'
                    }`}>
                      {step.label}
                    </h4>
                    
                    {output?.confidence && (
                      <span className="text-xs bg-void px-2 py-1 rounded text-accent font-mono border border-border">
                        Conf: {(output.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                  
                  {output?.reasoning && (
                    <div className="text-sm text-text-dim mt-2 flex items-start gap-2 bg-void p-3 rounded-md border border-border/50">
                      <ChevronRight className="w-4 h-4 text-accent shrink-0 mt-0.5" />
                      <p>{output.reasoning}</p>
                    </div>
                  )}
                  
                  {status === 'running' && !output?.reasoning && (
                     <div className="text-sm text-text-dim mt-2 flex items-center gap-2">
                       <span className="animate-pulse">Agent is thinking...</span>
                     </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default AgentFlowVisualizer;
