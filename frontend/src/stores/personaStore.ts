import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UserPersona } from '@/types';

interface PersonaStore {
  selectedPersona: UserPersona | null;
  setPersona: (persona: UserPersona | null) => void;
  clearPersona: () => void;
}

export const usePersonaStore = create<PersonaStore>()(
  persist(
    (set) => ({
      selectedPersona: null,
      setPersona: (persona) => set({ selectedPersona: persona }),
      clearPersona: () => set({ selectedPersona: null }),
    }),
    {
      name: 'persona-storage',
    }
  )
);
