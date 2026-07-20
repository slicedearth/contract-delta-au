export interface Version {
  contract_id: string;
  notice_id: string;
  source_release_id: string;
  source_modified_at: string;
  source_url: string;
  source_hash: string;
  agency_name: string;
  supplier_name: string;
  title: string | null;
  description: string;
  category_code: string | null;
  procurement_method: string | null;
  reported_value: string | null;
  currency: string;
  contract_start_date: string | null;
  contract_end_date: string | null;
}

export interface ChangeEvent {
  event_id: string;
  contract_id: string;
  notice_id: string;
  detected_at: string;
  field_name: string;
  field_label: string;
  old_value: string | null;
  new_value: string | null;
  absolute_change: string | null;
  percentage_change: string | null;
  duration_change_days: number | null;
  before_release_id: string;
  after_release_id: string;
  before_source_hash: string;
  after_source_hash: string;
  source_url: string;
  source_license: string;
  source_publisher: string;
  adaptation_notice: string;
  direction: string;
  summary: string;
  agency_name?: string;
  supplier_name?: string;
  description?: string;
}

export interface Contract {
  contract_id: string;
  notice_id: string;
  agency_name: string;
  supplier_name: string;
  title: string | null;
  description: string;
  category_code: string | null;
  procurement_method: string | null;
  currency: string;
  original_reported_value: string | null;
  current_reported_value: string | null;
  value_change: string | null;
  value_change_percentage: string | null;
  contract_start_date: string | null;
  contract_end_date: string | null;
  latest_modified_at: string;
  amendment_count: number;
  source_url: string;
  evidence_path: string;
  versions: Version[];
  events: ChangeEvent[];
}

export interface Summary {
  name: string;
  contracts: number;
  events: number;
  reported_value: string;
}

export interface Dashboard {
  generated_at: string;
  latest_source_modified_at: string | null;
  source: { name: string; publisher: string; license: string; adaptation_notice: string };
  disclaimer: string;
  stats: {
    changed_contracts: number;
    change_events: number;
    amendments_tracked: number;
    current_reported_value: string;
  };
  events: ChangeEvent[];
  contracts: Contract[];
  agencies: Summary[];
  suppliers: Summary[];
}
