import numpy as np
import qcodes as qc
import broadbean as bb
from broadbean.plotting import plotter

from pytopo.awg_sequencing import broadbean as bbtools
from pytopo.awg_sequencing.broadbean import BluePrints, BroadBeanSequence

ramp = bb.PulseAtoms.ramp
sine = bb.PulseAtoms.sine


class AlazarTestSequence(BroadBeanSequence):
    """
    A sequence that plays a pulse train of sine waves. 
    before each pulse we emit a trigger on a marker. 
    for each pulse in the sequence we can set time, frequency, phase, and amplitude.

    required channels:
        'pulse' : analog output
        'ats_trigger' : marker output
    """

    name = 'alazar_test_sequence'

    def sequence(self, pulse_times, frequencies, phases, amplitudes,
                 cycle_time=40e-6, pre_trig_time=0.1e-6, trig_time=0.1e-6):
        """
        Parameters:
        ----------                
            pulse times : sequence
                pulse times (in sec.)

            frequencies : sequence
                pulse frequencies (in Hz)

            phases : sequence
                pulse phases (in radians)

            amplitudes : sequence
                pulse amplitudes

            cycle_time : numeric, in s (default: 40e-6)
                time per pulse element (in sec.)
                difference between pulse time and cycle time results in 0 output for that time.

            pre_trig_time : numeric, in s (default: 100e-9)
                delay time before anything happens in the sequence.

            trig_time : numeric, in s (default: 100e-9)
                length of the trigger pulse. (the signal pulse starts after the trigger
                pulse ends.)
        """

        pulse_times = np.array(pulse_times)
        low_times = cycle_time - pulse_times - pre_trig_time - trig_time

        elements = []
        for pulse_time, low_time, frq, phase, amp in zip(pulse_times, low_times, frequencies, phases, amplitudes):
            bps = bbtools.BluePrints(
                chan_map=self.chan_map, length=cycle_time, sample_rate=self.SR)
            bps['pulse'].insertSegment(0, ramp, (0, 0), dur=pre_trig_time)
            bps['pulse'].insertSegment(
                1, ramp, (0, 0), name='trigger', dur=trig_time)
            bps['pulse'].insertSegment(
                2, sine, (frq, amp, 0, phase), name='pulse', dur=pulse_time)
            bps['pulse'].insertSegment(3, ramp, (0, 0), dur=low_time)
            bps['ats_trigger'] = [(pre_trig_time, trig_time)]
            elements.append(bbtools.blueprints2element(bps))

        return bbtools.elements2sequence(elements, self.name)


class TriggerSequence(BroadBeanSequence):
    """
    a sequence that consists of a single trigger element.

    required channels:
        'pulse' : analog output (for the 'debug' signal)
        'ats_trigger' : marker output
        'ro_trigger' : readout trigger (optional)
    """
    name = 'trigger_sequence'

    def sequence(self, trig_time=1e-6, cycle_time=10e-6,
                 pre_trig_time=1e-6, ncycles=1, nreps_per_cycle=1,
                 debug_signal=False, ro_trigger_always_on=False):
        """
        :param trig_time: length of the trigger pulse [s]
        :param cycle_time: length of each element [s]
        :param pre_trig_time: buffer between start of the element and start of the trigger [s]
        :param ncycles: how many elements to generate
        :param nreps_per_cycle: repetitions per element
        :param debug_signal: if True, and channel ``pulse`` is defined, play a sine wave 
                             of f = 1 MHz on that.
        :param ro_trigger_always_on: if True (and ``ro_trigger`` defined), ro trigger is 
                                     always on (no pre/post buffer).
        """

        end_buffer = 1e-6
        low_time = cycle_time - trig_time - pre_trig_time - end_buffer

        elements = []
        for i in range(ncycles):
            bps = bbtools.BluePrints(
                chan_map=self.chan_map, length=cycle_time, sample_rate=self.SR)
            if debug_signal:
                bps['pulse'].insertSegment(0, ramp, (0, 0), dur=pre_trig_time)
                bps['pulse'].insertSegment(
                    1, ramp, (0, 0), name='trigger', dur=trig_time)
                bps['pulse'].insertSegment(
                    2, sine, (1e6, 0.5, 0, 0), name='dbg_pulse', dur=low_time)
                bps['pulse'].insertSegment(3, ramp, (0, 0), dur=end_buffer)
            else:
                bps['pulse'].insertSegment(0, ramp, (0, 0), dur=cycle_time)

            bps['ats_trigger'] = [(pre_trig_time, trig_time)]
            if 'ro_trigger' in bps.map:
                if ro_trigger_always_on:
                    t0, t1 = 0, cycle_time
                else:
                    t0, t1 = pre_trig_time + trig_time, low_time
                bps['ro_trigger'] = [(t0, t1)]
            else:
                print('ro_trigger not defined. omitting.')

            for k, v in bps.map.items():
                if '_trigger' in k and k not in ['ats_trigger', 'ro_trigger']:
                    t0, t1 = pre_trig_time + trig_time, low_time
                    bps[k] = [(t0, t1)]

            elements.append(bbtools.blueprints2element(bps))

        seq = bbtools.elements2sequence(elements, self.name)

        for i in range(ncycles):
            seq.setSequencingNumberOfRepetitions(i+1, nreps_per_cycle)

        return seq
