"""Team Decul's possession pipeline.

Planned layers, each measured on its own before the next is added:

  1. cleaning   -- ball interpolation over short gaps, metres, duplicate tracks
  2. features   -- per-frame distances, speeds, ball-out, Smart Tagging priors
  3. evidence   -- per-frame scores for H, A and D
  4. decoding   -- Viterbi over each half, with a cost for every change of state

make_submission.py at the repository root is the only entry point.
"""
