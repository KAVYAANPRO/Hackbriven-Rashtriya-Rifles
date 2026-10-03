import { createContext, useContext, useState, useCallback } from 'react';
import { JOB_STATUS } from '../constants/jobs';

const JobsContext = createContext(null);

export function JobsProvider({ children }) {
  const [jobs, setJobs] = useState([]);
  const [activeJobId, setActiveJobId] = useState(null);

  const addJob = useCallback((job) => {
    setJobs((prev) => [job, ...prev]);
    setActiveJobId(job.id);
  }, []);

  const updateJob = useCallback((id, updates) => {
    setJobs((prev) => prev.map((j) => (j.id === id ? { ...j, ...updates } : j)));
  }, []);

  const removeJob = useCallback((id) => {
    setJobs((prev) => prev.filter((j) => j.id !== id));
    setActiveJobId((prev) => (prev === id ? null : prev));
  }, []);

  const getJob = useCallback((id) => jobs.find((j) => j.id === id), [jobs]);

  const activeJobs = jobs.filter((j) =>
    [JOB_STATUS.PENDING, JOB_STATUS.PROCESSING].includes(j.status)
  );

  return (
    <JobsContext.Provider value={{ jobs, activeJobs, activeJobId, addJob, updateJob, removeJob, getJob, setActiveJobId }}>
      {children}
    </JobsContext.Provider>
  );
}

export function useJobs() {
  const ctx = useContext(JobsContext);
  if (!ctx) throw new Error('useJobs must be used within JobsProvider');
  return ctx;
}
