import { useEffect, useState } from 'react';
import PromptStep from '../components/create/PromptStep.jsx';
import OptionsStep from '../components/create/OptionsStep.jsx';
import { useImages } from '../components/create/useImages.js';

// Two steps on one route: 1) the prompt, 2) language, motion tier, images and generate.
export default function Create() {
  const [step, setStep] = useState(1);
  const [dir, setDir] = useState('fwd');
  const images = useImages(); // lives here so the images survive Edit and back

  const to = (n) => {
    setDir(n > step ? 'fwd' : 'back');
    setStep(n);
  };

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [step]);

  return (
    <div className="cx-step" data-dir={dir} key={step}>
      {step === 1
        ? <PromptStep onSubmit={() => to(2)} />
        : <OptionsStep onEdit={() => to(1)} images={images} />}
    </div>
  );
}
