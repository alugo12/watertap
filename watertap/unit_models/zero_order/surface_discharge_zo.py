#################################################################################
# WaterTAP Copyright (c) 2020-2023, The Regents of the University of California,
# through Lawrence Berkeley National Laboratory, Oak Ridge National Laboratory,
# National Renewable Energy Laboratory, and National Energy Technology
# Laboratory (subject to receipt of any required approvals from the U.S. Dept.
# of Energy). All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and license
# information, respectively. These files are also available online at the URL
# "https://github.com/watertap-org/watertap/"
#################################################################################
"""
This module contains a zero-order representation of a surface discharge unit
operation.
"""

import pyomo.environ as pyo
from pyomo.environ import Reference, units as pyunits, Var
from idaes.core import declare_process_block_class

from watertap.core import build_pt, pump_electricity, ZeroOrderBaseData

# Some more information about this module
__author__ = "Travis Arnold"


@declare_process_block_class("SurfaceDischargeZO")
class SurfaceDischargeData(ZeroOrderBaseData):
    """
    Zero-Order model for a surface discharge unit operation.
    """

    CONFIG = ZeroOrderBaseData.CONFIG()

    def build(self):
        super().build()

        self._tech_type = "surface_discharge"
        build_pt(self)
        self._Q = Reference(self.properties[:].flow_vol)

        pump_electricity(self, self._Q)

        self.pipe_distance = Var(
            self.flowsheet().config.time, units=pyunits.miles, doc="Piping distance"
        )

        self.pipe_diameter = Var(
            self.flowsheet().config.time, units=pyunits.inches, doc="Pipe diameter"
        )

        self._fixed_perf_vars.append(self.pipe_distance)
        self._fixed_perf_vars.append(self.pipe_diameter)

        self._perf_var_dict["Pipe Distance"] = self.pipe_distance
        self._perf_var_dict["Pipe Diameter"] = self.pipe_diameter

    @property
    def default_costing_method(self):
        return self.cost_surface_discharge

    @staticmethod
    def cost_surface_discharge(blk):
        """
        General method for costing surface discharge. Capital cost is based on
        construction and pipe costs.
        """

        t0 = blk.flowsheet().time.first()

        # Get parameter dict from database
        parameter_dict = blk.unit_model.config.database.get_unit_operation_parameters(
            blk.unit_model._tech_type, subtype=blk.unit_model.config.process_subtype
        )

        # Get costing parameter sub-block for this technology
        A, B, pipe_cost_basis, ref_state = blk.unit_model._get_tech_parameters(
            blk,
            parameter_dict,
            blk.unit_model.config.process_subtype,
            [
                "capital_a_parameter",
                "capital_b_parameter",
                "pipe_cost_basis",
                "reference_state",
            ],
        )

        # Add cost variable and constraint
        blk.capital_cost = pyo.Var(
            initialize=1,
            units=blk.config.flowsheet_costing_block.base_currency,
            bounds=(0, None),
            doc="Capital cost of unit operation",
        )

        expr = pyo.units.convert(
            A
            * pyo.units.convert(
                blk.unit_model.properties[t0].flow_vol / ref_state,
                to_units=pyo.units.dimensionless,
            )
            ** B,
            to_units=blk.config.flowsheet_costing_block.base_currency,
        ) + pyo.units.convert(
            pipe_cost_basis
            * blk.unit_model.pipe_distance[t0]
            * blk.unit_model.pipe_diameter[t0],
            to_units=blk.config.flowsheet_costing_block.base_currency,
        )

        blk.unit_model._add_cost_factor(
            blk, parameter_dict["capital_cost"]["cost_factor"]
        )

        blk.capital_cost_constraint = pyo.Constraint(
            expr=blk.capital_cost == blk.cost_factor * expr
        )

        # Register flows
        blk.config.flowsheet_costing_block.cost_flow(
            blk.unit_model.electricity[t0], "electricity"
        )
