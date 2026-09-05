"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CaseRecord } from "@/lib/types";

export function useAuthorizedCase() {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [record, setRecord] = useState<CaseRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    api.cases()
      .then(async (authorized) => {
        setCases(authorized);
        if (authorized[0]) setRecord(await api.case(authorized[0].caseNumber));
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false));
  }, []);

  return { cases, record, loading, error };
}
