import { Fragment } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface FilterDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  children: React.ReactNode;
  activeFilterCount: number;
  onClearAll: () => void;
  onApply: () => void;
}

export function FilterDrawer({
  isOpen,
  onClose,
  children,
  activeFilterCount,
  onClearAll,
  onApply,
}: FilterDrawerProps) {
  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0">
          <div className="flex h-full items-end justify-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="translate-y-full"
              enterTo="translate-y-0"
              leave="ease-in duration-200"
              leaveFrom="translate-y-0"
              leaveTo="translate-y-full"
            >
              <Dialog.Panel className="flex h-[85vh] w-full max-w-md flex-col bg-white shadow-2xl">
                {/* Header */}
                <div className="flex items-center justify-between border-b border-stone-200 px-6 py-4">
                  <div className="flex items-center gap-3">
                    <Dialog.Title className="font-serif text-xl font-semibold text-stone-900">
                      Filters
                    </Dialog.Title>
                    {activeFilterCount > 0 && (
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-stone-900 text-xs font-medium text-white">
                        {activeFilterCount}
                      </span>
                    )}
                  </div>

                  <button
                    onClick={onClose}
                    className="rounded-full p-2 text-stone-600 hover:bg-stone-100 hover:text-stone-900"
                    aria-label="Close"
                  >
                    <X className="h-5 w-5" />
                  </button>
                </div>

                {/* Filter content - scrollable */}
                <div className="flex-1 overflow-y-auto px-6 py-6">
                  <div className="space-y-8">{children}</div>
                </div>

                {/* Footer with actions */}
                <div className="border-t border-stone-200 px-6 py-4">
                  <div className="flex gap-3">
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={onClearAll}
                      disabled={activeFilterCount === 0}
                    >
                      Clear All
                    </Button>
                    <Button
                      className="flex-1"
                      onClick={() => {
                        onApply();
                        onClose();
                      }}
                    >
                      Apply {activeFilterCount > 0 && `(${activeFilterCount})`}
                    </Button>
                  </div>
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
}
