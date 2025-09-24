/**
 * Audit Logs Page
 * 
 * Main page for viewing system audit logs.
 * Integrates with: AuditLogViewer component
 */

import { Metadata } from 'next';
import { AuditLogViewer } from '@/components/audit/AuditLogViewer';
import { Separator } from '@/components/ui/separator';

export const metadata: Metadata = {
  title: 'Audit Logs | WDFWatch',
  description: 'View system activity and audit trail',
};

export default function AuditPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Audit Logs</h1>
        <p className="text-muted-foreground mt-2">
          Track all actions and changes made in the system
        </p>
      </div>
      
      <Separator />
      
      <AuditLogViewer />
    </div>
  );
}